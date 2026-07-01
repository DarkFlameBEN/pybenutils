import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List
import pyperclip
from psutil import NoSuchProcess
from pybenutils.utils_logger.config_logger import get_logger
from pybenutils.os_operations.process import ProcessHandler
from pybenutils.os_operations.window_operations import get_hwnds_by_class, click_on_point
from pybenutils.browsers.windows_browsers_keywords import set_browser_url, close_browser, get_to_home_page, \
    open_browser_windows
if sys.platform == 'win32':
    import win32com.client
    import win32gui
elif sys.platform == 'darwin':
    from pybenutils.os_operations.mac_operations import run_apple_script
elif sys.platform == 'linux':
    # Mac helpers are not imported on Linux - we use xdotool/xdg-open instead.
    # All osascript-based paths are bypassed by explicit `elif sys.platform == 'linux'`
    # branches added throughout this module.
    pass

logger = get_logger()


def _linux_run(cmd, check=False, capture=True, timeout=10):
    """Run shell command on Linux and return CompletedProcess.

    :param cmd: list or str command
    :param check: raise on non-zero exit
    :param capture: capture stdout/stderr
    :param timeout: seconds
    """
    try:
        return subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            check=check,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
    except Exception as ex:
        logger.error(f'_linux_run failed: cmd={cmd} err={ex}')
        return None


def _xdotool(*args, timeout=10):
    """Invoke xdotool with the given args. Returns stdout str (empty on failure)."""
    if not shutil.which('xdotool'):
        logger.error('xdotool not installed. Run: sudo apt install xdotool')
        return ''
    res = _linux_run(['xdotool', *map(str, args)], timeout=timeout)
    if res and res.returncode == 0:
        return (res.stdout or '').strip()
    if res and res.stderr:
        logger.debug(f'xdotool stderr: {res.stderr.strip()}')
    return ''


def _xdotool_activate(window_name):
    """Activate (focus + raise) a window by name match (case-insensitive)."""
    wid = _xdotool('search', '--name', window_name)
    if not wid:
        return False
    # search returns one wid per line; take last (newest)
    wid = wid.splitlines()[-1].strip()
    _xdotool('windowactivate', '--sync', wid)
    return True


# Map of Windows SendKeys named keys to xdotool keysyms
_WIN_SENDKEYS_NAMED = {
    'F1': 'F1', 'F2': 'F2', 'F3': 'F3', 'F4': 'F4', 'F5': 'F5', 'F6': 'F6',
    'F7': 'F7', 'F8': 'F8', 'F9': 'F9', 'F10': 'F10', 'F11': 'F11', 'F12': 'F12',
    'ENTER': 'Return',
    'TAB': 'Tab',
    'ESC': 'Escape',
    'BACKSPACE': 'BackSpace', 'BS': 'BackSpace', 'BKSP': 'BackSpace',
    'DEL': 'Delete', 'DELETE': 'Delete',
    'HOME': 'Home',
    'END': 'End',
    'PGUP': 'Prior',
    'PGDN': 'Next',
    'INS': 'Insert', 'INSERT': 'Insert',
    'LEFT': 'Left', 'RIGHT': 'Right', 'UP': 'Up', 'DOWN': 'Down',
    'SPACE': 'space',
    '-': 'minus', '+': 'plus',
    '{': 'braceleft', '}': 'braceright',
    '[': 'bracketleft', ']': 'bracketright',
    '(': 'parenleft', ')': 'parenright',
    '^': 'asciicircum', '%': 'percent', '~': 'asciitilde',
}


def _sendkeys_to_xdotool_chord(text):
    """Parse a Windows-style SendKeys string into a list of xdotool key chords.

    Returns None if `text` looks like a literal string (no SendKeys metacharacters),
    so the caller can fall back to `xdotool type`.

    Supported subset (sufficient for pybenutils browser keywords):
      {KEYNAME}      -> single named key (e.g. {F5}, {ENTER}, {TAB})
      ^x             -> Ctrl+x  (single character)
      +x             -> Shift+x
      %x             -> Alt+x
      ^+{KEY}        -> Ctrl+Shift+key
      ^{KEY}         -> Ctrl+key
      Sequences may be concatenated, e.g. "^+{K}", "^t", "{F5}"
    """
    # Quick reject — if no SendKeys metachar present, treat as plain text.
    if not any(c in text for c in ('{', '^', '+', '%', '~')):
        return None
    # Heuristic: if the entire string is wrapped braces or starts with a modifier
    # / brace, try to parse. Otherwise it's likely text containing a stray char.
    if not (text.startswith('{') or text.startswith('^') or text.startswith('+')
            or text.startswith('%') or text.startswith('~')):
        return None

    chords = []
    i = 0
    while i < len(text):
        mods = []
        # collect modifiers
        while i < len(text) and text[i] in ('^', '+', '%'):
            mods.append({'^': 'ctrl', '+': 'shift', '%': 'alt'}[text[i]])
            i += 1
        if i >= len(text):
            break
        ch = text[i]
        if ch == '{':
            # find closing brace
            end = text.find('}', i)
            if end == -1:
                return None
            keyname = text[i + 1:end].strip().upper()
            keysym = _WIN_SENDKEYS_NAMED.get(keyname, keyname)
            i = end + 1
        else:
            # single literal char following modifiers
            keysym = ch
            i += 1
        chord = '+'.join(mods + [keysym]) if mods else keysym
        chords.append(chord)
    return chords if chords else None


# Mapping from generic browser name to Linux binary name (used to launch / pgrep).
LINUX_BROWSER_BINARY_TABLE = {
    'chrome': 'google-chrome',
    'chromium': 'chromium-browser',
    'firefox': 'firefox',
    'msedge': 'microsoft-edge',
}
# Mapping from generic browser name to the visible window title fragment used
# by xdotool to focus the window.
LINUX_BROWSER_WINDOW_NAME_TABLE = {
    'chrome': 'Google Chrome',
    'chromium': 'Chromium',
    'firefox': 'Mozilla Firefox',
    'msedge': 'Microsoft Edge',
}


def kill_all_browsers(browsers_list=('iexplore.exe', 'IEDriverServer.exe', 'chrome', 'firefox', 'chromedriver',
                                     'safari', 'chromium', 'geckodriver', 'msedge'),
                      attempt_graceful_shutdown=True):
    """Closes and kills all the process sharing the given process names in the input list

    :param browsers_list: Browsers process name to kill
    :param attempt_graceful_shutdown: Attempts to close the browser before killing its processes
    """
    if type(browsers_list) == str:
        browsers_list = [browsers_list]
    for browser in browsers_list:
        brw = SimpleBrowserController(browser)
        brw.kill(attempt_graceful_shutdown=attempt_graceful_shutdown)
        time.sleep(5)


def close_all_browsers(browsers_list=('iexplore.exe', 'IEDriverServer.exe', 'chrome', 'firefox', 'chromedriver',
                                      'safari', 'chromium', 'geckodriver', 'msedge')):
    """Closes all the process sharing the given process names in the input list

    :param browsers_list: Browsers process name to kill
    """
    if type(browsers_list) == str:
        browsers_list = [browsers_list]
    for browser in browsers_list:
        brw = SimpleBrowserController(browser)
        brw.close()
        time.sleep(5)


class SimpleBrowserController:
    def __init__(self, browser_name):
        """Initiates the class

        :param browser_name: In Windows, process name. In mac: Full application path OR one of the pre-supported apps.
         Supported apps: safari, chrome, chromium, firefox, msedge
        """
        process_names_mac_conversion_table = {
            'safari': 'Safari',
            'chrome': 'Google Chrome',
            'chromium': 'Chromium',
            'firefox': 'Firefox',
            'msedge': 'Microsoft Edge'
        }
        mac_application_path_conversion_table = {
            'safari': '/Applications/Safari.app',
            'chrome': '/Applications/Google Chrome.app',
            'chromium': '{home}/Applications/Chromium.app'.format(home=Path.home()),
            'firefox': '/Applications/Firefox.app',
            'msedge': '/Applications/Microsoft Edge.app'
        }
        class_name_windows_conversion_table = {
            'chromedriver.exe': 'Chrome_WidgetWin_1',
            'chrome.exe': 'Chrome_WidgetWin_1',
            'firefox.exe': 'MozillaWindowClass',
            'geckodriver.exe': 'MozillaWindowClass',
            'iexplore.exe': 'IEFrame',
            'IEDriverServer.exe': 'IEFrame',
            'msedge.exe': 'Chrome_WidgetWin_1'
        }
        self.browser_name = browser_name
        # Remember the original key (e.g. 'chrome') for Linux lookups
        self._browser_key = browser_name
        if sys.platform == 'darwin' and browser_name in process_names_mac_conversion_table:
            self.browser_name = process_names_mac_conversion_table[browser_name]
        self.mac_browser_path = mac_application_path_conversion_table.get(browser_name, '')

        # Linux-specific lookups
        self.linux_binary = LINUX_BROWSER_BINARY_TABLE.get(browser_name, browser_name)
        self.linux_window_name = LINUX_BROWSER_WINDOW_NAME_TABLE.get(browser_name, browser_name)

        self.browser_process_name = self.browser_name
        if self.browser_name in ['chrome', 'chrome.exe', 'chromium', 'chromium.exe']:
            self.browser_process_name = 'chrome.exe'
        elif sys.platform == 'win32' and not self.browser_process_name.endswith('.exe'):
            self.browser_process_name = '{brw}.exe'.format(brw=self.browser_process_name)
        # On Linux the process name is the binary name (no .exe), e.g. 'chrome' / 'firefox'.
        if sys.platform == 'linux':
            # Default to the short browser key so ProcessHandler matches "chrome" etc.
            self.browser_process_name = self._browser_key

        self.hwnd = []
        self.app_obj = None
        if sys.platform == 'darwin':
            from pybenutils.os_operations.mac_application_control import ApplicationControl
            self.app_obj = ApplicationControl(self.mac_browser_path)
        elif sys.platform == 'linux':
            # No equivalent ApplicationControl on Linux; we manage via subprocess + xdotool.
            self.app_obj = None
        else:
            self.class_name = class_name_windows_conversion_table[self.browser_process_name] if \
                self.browser_process_name in class_name_windows_conversion_table else ''

    def launch(self, arguments=()) -> bool:
        """Launching the app
        :param arguments: launch shell arguments
        """
        logger.info('Launching browser: {brw}{arg}'.format(
            brw=self.browser_name, arg=f' With args: {arguments}' if arguments else ''))
        if sys.platform == 'win32':
            new_handler = open_browser_windows(browser=self.browser_name, arguments=arguments)
            if not new_handler:
                return False
            self.hwnd.append(new_handler)
            return True
        elif sys.platform == 'linux':
            binary = self.linux_binary if shutil.which(self.linux_binary) else self._browser_key
            if not shutil.which(binary):
                logger.error(f'Browser binary not found in PATH: {binary}')
                return False
            # Build chrome-specific args:
            # - --ozone-platform=x11 forces X11 backend (else chrome attaches to
            #   the user's Wayland session and renders on the real desktop :0)
            # - --user-data-dir=<tmp> isolates from the user's existing chrome
            #   profile (chrome's singleton would otherwise forward our URL to
            #   the running chrome on :0 instead of opening a window on our :100)
            # - --no-first-run / --no-default-browser-check suppress modal dialogs
            chrome_force_x11 = []
            if 'chrome' in binary or 'chromium' in binary or 'edge' in binary:
                # Use a fixed persistent profile dir so site permissions
                # (granted manually once) survive across test runs.
                # If env var PYBENUTILS_CHROME_PROFILE is set, use that;
                # otherwise default to ~/gpa_chrome_profile.
                persistent_profile = os.environ.get(
                    'PYBENUTILS_CHROME_PROFILE',
                    os.path.expanduser('~/gpa_chrome_profile')
                )
                os.makedirs(persistent_profile, exist_ok=True)
                chrome_force_x11 = [
                    '--ozone-platform=x11',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    f'--user-data-dir={persistent_profile}',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--new-window',
                    '--window-size=1280,1024',
                    # Auto-launch eaaclient:// protocol from the Akamai IDP origin
                    # without prompting. Matches the Chrome enterprise policy
                    # AutoLaunchProtocolsFromOrigins but as a cmdline override.
                    '--auto-launch-protocols-from-origins='
                    'eaaclient,https://etp-client.login.go.akamai-access.com',
                    # Bypass the "request blocked" page by treating the IDP origin
                    # as a secure origin and disabling popup blocking for it.
                    '--disable-popup-blocking',
                    # Suppress "Chrome didn't shut down correctly" Restore popup
                    # that blocks the IDP page after profile clone.
                    '--disable-session-crashed-bubble',
                    '--disable-features=InfiniteSessionRestore',
                    '--hide-crash-restore-bubble',
                    # NOTE: --incognito tried earlier but broke first-auth
                    # because incognito doesn't load the profile permissions
                    # (Allow popup gets re-asked). The cloned profile's
                    # cookies/permissions are required.
                ]
            cmd = [binary, *chrome_force_x11, *map(str, arguments)] if arguments else \
                  [binary, *chrome_force_x11]
            # Strip Wayland env so chrome falls back to X11 (DISPLAY only).
            child_env = os.environ.copy()
            for var in ('WAYLAND_DISPLAY', 'XDG_SESSION_TYPE', 'GDK_BACKEND',
                        'QT_QPA_PLATFORM', 'CLUTTER_BACKEND', 'MOZ_ENABLE_WAYLAND'):
                child_env.pop(var, None)
            # Ensure DISPLAY is set; xvfb-run exports it.
            if 'DISPLAY' not in child_env:
                logger.warning('DISPLAY env not set; xdotool focus will fail. Run under xvfb-run.')
            logger.info(f'Linux launch: {" ".join(cmd)} (DISPLAY={child_env.get("DISPLAY","<unset>")})')
            try:
                # Detach so the test can continue while browser runs
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL, start_new_session=True,
                                 env=child_env)
            except Exception as ex:
                logger.error(f'Failed to launch {binary}: {ex}')
                return False
            # Give chrome time to actually map its window in xvfb
            for attempt in range(20):
                time.sleep(1)
                wid = _xdotool('search', '--name', self.linux_window_name)
                if wid:
                    logger.info(f'Linux chrome window appeared on DISPLAY '
                                f'{child_env.get("DISPLAY","?")} after {attempt+1}s '
                                f'(wid={wid.splitlines()[-1]})')
                    return True
            # Last-chance diagnostic — list all windows so we know what xdotool can see
            all_wins = _xdotool('search', '--onlyvisible', '--name', '.+')
            logger.warning(f'Linux chrome window NOT found after 20s. '
                           f'xdotool sees these visible windows: {all_wins!r}')
            return False
        else:
            return self.app_obj.launch(arguments=arguments)

    def kill(self, attempt_graceful_shutdown=True):
        """Killing the browser processes
        :param attempt_graceful_shutdown: Try to gracefully close the browser before killing it
        """
        if attempt_graceful_shutdown:
            self.close()
            time.sleep(20)
        logger.info('Killing {brw} browser instances'.format(brw=self.browser_process_name))
        if sys.platform == 'win32':
            p_handler = ProcessHandler(self.browser_process_name)
            try:
                p_handler.kill_process()
            except NoSuchProcess as ex:
                logger.warning(ex)
                time.sleep(20)
                self.kill(attempt_graceful_shutdown=attempt_graceful_shutdown)
            self.hwnd = []
        elif sys.platform == 'linux':
            # pkill matches by process name. -f matches full command line which is
            # safer for snap chrome wrappers etc.
            _linux_run(['pkill', '-f', self.linux_binary], timeout=5)
            time.sleep(1)
            _linux_run(['pkill', '-9', '-f', self.linux_binary], timeout=5)
        else:
            self.app_obj.kill()
        time.sleep(10)
        if ProcessHandler(self.browser_process_name).proc_list:
            logger.warning('Some processes of {na} stayed alive'.format(na=self.browser_process_name))

    def close(self) -> bool:
        """Try to gracefully close the browser
        :return: True if successful
        """
        logger.info('Trying to close the {brw} browser instances'.format(brw=self.browser_name))
        if sys.platform == 'win32':
            if close_browser(self.browser_name):
                self.hwnd = []
                return True
            self.press_enter_button()
            time.sleep(3)
            if close_browser(self.browser_name):
                self.hwnd = []
                return True
            logger.warning('{n} could not be gracefully closed'.format(n=self.browser_name))
            return False
        elif sys.platform == 'linux':
            # Try graceful SIGTERM first; pkill returns 0 if any process matched.
            _linux_run(['pkill', '-TERM', '-f', self.linux_binary], timeout=5)
            time.sleep(3)
            return True
        else:
            self.app_obj.close()
            time.sleep(3)
            return True

    def refresh_hwnd_list(self) -> List:
        self.hwnd = get_hwnds_by_class(self.class_name)
        return self.hwnd

    def get_hwnd(self) -> List:
        """Returns the hwnd list parameter"""
        return self.hwnd

    def _linux_focus_browser(self) -> bool:
        """Bring the browser window to focus on Linux using xdotool. Returns True if found."""
        found = _xdotool_activate(self.linux_window_name)
        if not found:
            logger.warning(f'_linux_focus_browser: no window matching "{self.linux_window_name}". '
                           f'xdotool search returned empty. Browser may not be visible to X server.')
        return found

    def press_key_on_linux_browser(self, keysym) -> bool:
        """Send an xdotool 'key' chord (e.g. 'ctrl+l', 'Return', 'F6') to the focused browser window.

        :param keysym: xdotool keysym or chord
        :return: True on success
        """
        try:
            self._linux_focus_browser()
            logger.debug(f'xdotool key: {keysym}')
            _xdotool('key', '--clearmodifiers', keysym)
            return shutil.which('xdotool') is not None
        except Exception as ex:
            logger.error(f'press_key_on_linux_browser failed key={keysym} err={ex}')
            return False

    def type_text_on_linux_browser(self, text, delay_ms=25) -> bool:
        """Type literal text into the focused browser window using xdotool type.

        :param text: text to type
        :param delay_ms: per-char delay
        :return: True on success
        """
        try:
            self._linux_focus_browser()
            # Redact obvious secrets from logs (passwords are commonly typed via this path)
            preview = text if len(text) <= 60 else f'{text[:60]}...({len(text)} chars)'
            logger.debug(f'xdotool type: "{preview}"')
            _xdotool('type', '--clearmodifiers', '--delay', str(delay_ms), text)
            return shutil.which('xdotool') is not None
        except Exception as ex:
            logger.error(f'type_text_on_linux_browser failed: {ex}')
            return False

    def press_key_combination_on_mac_browser(self, key_command) -> bool:
        """Attempts to press the requested command on the keyboard using Applescript

        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                # logger.warning('You are trying to use a mac function on a windows os')
                return False
            elif sys.platform == 'linux':
                # Translate common Mac key codes to xdotool keysyms. Best-effort —
                # anything unknown logs and returns False so callers don't crash.
                mapping = {
                    'key code 96': 'F5',                          # reload
                    'key code 97 using option down': 'F6',        # focus url bar
                    'key code 76': 'Return',
                    'key code 53 using option down': 'Escape',
                    'key code 48': 'Tab',
                    'key code 48 using control down': 'ctrl+Tab',
                    'key code 17 using command down': 'ctrl+t',   # new tab
                    'key code 82 using command down': 'ctrl+0',   # zoom reset
                    'key code 78 using command down': 'ctrl+minus',
                    'key code 69 using command down': 'ctrl+plus',
                    'key code 121': 'Next',
                    'key code 116': 'Prior',
                    'key code 115 using command down': 'ctrl+Home',
                    'key code 119 using command down': 'ctrl+End',
                    'key code 0 using command down': 'ctrl+a',
                    'key code 37 using command down': 'ctrl+l',
                    'keystroke "c" using command down': 'ctrl+c',
                    'key code 4 using {command down, shift down}': 'ctrl+shift+h',
                    'key code 115 using option down': 'alt+Home',
                }
                key = mapping.get(key_command)
                if key:
                    return self.press_key_on_linux_browser(key)
                # Handle keystroke "literal text" pattern
                if key_command.startswith('keystroke "') and key_command.endswith('"'):
                    return self.type_text_on_linux_browser(key_command[11:-1])
                logger.debug(f'press_key_combination_on_mac_browser: no Linux mapping for "{key_command}"')
                return False
            else:
                cmd = f"""
                set chExist to false
                set appName to "{self.browser_name}"
                tell application "System Events"
                    if (name of processes) contains appName then
                        set chExist to true
                    end if
                end tell
                
                if chExist then
                    tell application appName to activate
                    tell application "System Events" to {key_command}
                    return true
                end if
                return false
                """
                result = run_apple_script(cmd)
                if not result:
                    raise Exception('The Apple script has failed')
        except Exception as ex:
            logger.error('Failed to press requested keys {key} for error: {err}'.format(key=key_command, err=str(ex)))
            return False
        return True

    def get_to_home_page(self) -> bool:
        """Attempts to navigate to the home page using the keyboard shortcut keys

        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                errors = []
                if not self.hwnd:
                    self.refresh_hwnd_list()
                for hwnd in self.hwnd:
                    try:
                        get_to_home_page(hwnd)
                        break
                    except Exception as ex:
                        errors.append(str(ex))
                else:
                    logger.error('Failed to click on HOME button for errors: {err}'.format(err=errors))
            elif sys.platform == 'linux':
                # Most browsers on Linux use Alt+Home for home page
                return self.press_key_on_linux_browser('alt+Home')
            else:
                if 'firefox' in self.browser_name.lower():
                    return self.press_key_combination_on_mac_browser('key code 115 using option down')
                else:
                    return self.press_key_combination_on_mac_browser('key code 4 using {command down, shift down}')
        except Exception as ex:
            logger.error(f'Failed to press on the HOME button for error: {ex}')
            return False
        return True

    def press_esc_button(self) -> bool:
        """Attempts to press the ESC button on the keyboard

        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("{ESC}", 1)
            elif sys.platform == 'linux':
                return self.press_key_on_linux_browser('Escape')
            else:
                return self.press_key_combination_on_mac_browser('key code 53 using option down')
        except Exception as ex:
            logger.error(f'Failed to press on the ESC button for error: {ex}')
            return False
        return True

    def press_enter_button(self) -> bool:
        """Attempts to press the ENTER button on the keyboard

        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("{ENTER}", 1)
            elif sys.platform == 'linux':
                return self.press_key_on_linux_browser('Return')
            else:
                return self.press_key_combination_on_mac_browser('key code 76')
        except Exception as ex:
            logger.error(f'Failed to press on the ENTER button for error: {ex}')
            return False
        return True

    def send_keyboard_keys(self, text) -> bool:
        """Attempts to send the given text trough the keyboard
        :param text: The text to send to the browser
        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys(text, 1)
            elif sys.platform == 'linux':
                # The Mac/Win callers send strings in two distinct shapes:
                #   1. Literal text to type:  "etp.automation@gmail.com"
                #   2. Windows SendKeys notation: "{F5}", "^a", "^+{K}", "^t" etc.
                # xdotool's `type` is literal-only; `key` takes a chord. Translate
                # SendKeys-style sequences to xdotool key chords. Plain text falls
                # through to xdotool type.
                converted = _sendkeys_to_xdotool_chord(text)
                if converted is not None:
                    for chord in converted:
                        self.press_key_on_linux_browser(chord)
                else:
                    self.type_text_on_linux_browser(text)
            else:
                self.press_key_combination_on_mac_browser('keystroke "{text}"'.format(text=text))
        except Exception as ex:
            logger.error(f'Failed to send keys for error: {ex}')
            return False
        return True

    def get_browser_url(self) -> str:
        """Get Browser URL

        :return: browser URL
        """
        browser_url = ''
        try:
            if sys.platform == 'win32':
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("{F6}", 1)
            elif sys.platform == 'linux':
                # Ctrl+L focuses the address bar in Chrome/Firefox on Linux (F6 also works)
                self.press_key_on_linux_browser('ctrl+l')
            else:
                self.press_key_combination_on_mac_browser('key code 97 using option down')
        except Exception as ex:
            logger.error(f'Failed to press on the F6 button for error: {ex}')
            return browser_url
        time.sleep(2)
        try:
            if sys.platform == 'win32':
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("^c", 1)
            elif sys.platform == 'linux':
                self.press_key_on_linux_browser('ctrl+c')
            else:
                self.press_key_combination_on_mac_browser('keystroke "c" using command down')
        except Exception as ex:
            logger.error(f'Failed to copy browser URL (Ctrl/Cmd+C) for error: {ex}')
            return browser_url
        time.sleep(2)
        try:
            browser_url = pyperclip.paste()
        except Exception as ex:
            logger.error(f'Failed to read clipboard: {ex}')
        return browser_url if browser_url else ''  # Fix None type return bug

    def set_browser_url(self, url) -> bool:
        """Input the given url into the browser search line and press ENTER

        :param url: Text to be searched / Site url
        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                errors = []
                if not self.hwnd:
                    self.refresh_hwnd_list()
                for hwnd in self.hwnd:
                    try:
                        set_browser_url(hwnd, url)
                        break
                    except Exception as ex:
                        errors.append(str(ex))
                else:
                    logger.error('Failed to set browser url for errors: {err}'.format(err=errors))

            elif sys.platform == 'linux':
                self.press_key_on_linux_browser('ctrl+l')
                time.sleep(0.3)
                self.type_text_on_linux_browser(url)
                time.sleep(0.3)
                self.press_enter_button()
            else:
                self.press_key_combination_on_mac_browser('key code 37 using command down')
                self.send_keyboard_keys(url)
                self.press_enter_button()

        except Exception as ex:
            logger.error(f'Failed to set the browser url for error: {ex}')
            return False
        return True

    def switch_tab(self) -> bool:
        """Attempts to switch a tab using the keyboard
        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("^{TAB}", 1)
            elif sys.platform == 'linux':
                return self.press_key_on_linux_browser('ctrl+Tab')
            else:
                return self.press_key_combination_on_mac_browser('key code 48 using control down')
        except Exception as ex:
            logger.error(f'Failed to switch tabs for error: {ex}')
            return False
        return True

    def set_focus_by_mouse_click(self):
        """Set focus on browser window by clicking on it with the mouse

        :return: True if no exception had occurred assuming success
        """
        if sys.platform == 'win32':
            self.refresh_hwnd_list()
            for i in self.get_hwnd():
                try:
                    rect = win32gui.GetWindowRect(i)  # The window (0.0.0.0) point is at the top left corner
                    start_menu_safe_zone = win32gui.GetWindowRect(win32gui.GetDesktopWindow())[3] - rect[1] - 130 > 40
                    if rect != (0, 0, 0, 0) and win32gui.IsWindowVisible(i) and start_menu_safe_zone:
                        # Avoid trying to click on background processes
                        click_on_point(i, rect[0] + 10, rect[1] + 130)
                        return True
                except Exception as ex:
                    print(ex)
                    return False
        elif sys.platform == 'linux':
            # xdotool windowactivate is the closest analogue: brings window to front + focus.
            return self._linux_focus_browser()
        else:
            print('Not yet implemented')
            return False

    def send_console_command(self, command: str):
        """Sends console commands to the browser using keyboard navigation"""
        shell_send_keys_replacements = {'+': '{+}', '^': '{^}', '%': '{%}', '~': '{~}', '(': '{(}', ')': '{)}',
                                        '{': '{{}', '}': '{}}', '[': '{[}', ']': '{]}'}
        if sys.platform == 'win32':
            command = ''.join([shell_send_keys_replacements.get(c, c) for c in command])
            if 'firefox' in self.browser_name.lower():
                self.send_keyboard_keys('^+{K}')
                time.sleep(1)
                self.set_focus_by_mouse_click()
                self.send_keyboard_keys('^+{K}')
                time.sleep(1)
                self.send_keyboard_keys(command)
                time.sleep(1)
                self.press_enter_button()
                time.sleep(1)
                self.send_keyboard_keys('{F12}')
            elif 'chrome' in self.browser_name.lower():
                self.send_keyboard_keys('^+{j}')
                time.sleep(2)
                self.send_keyboard_keys(command)
                time.sleep(1)
                self.press_enter_button()
                time.sleep(1)
                self.send_keyboard_keys('{F12}')
            else:
                raise AssertionError(f'The requested operation is not yet implemented for {self.browser_name}')
        elif sys.platform == 'linux':
            # Linux: open DevTools console, type command, Enter, close DevTools
            if 'firefox' in self.browser_name.lower():
                self.press_key_on_linux_browser('ctrl+shift+k')
            else:
                self.press_key_on_linux_browser('ctrl+shift+j')
            time.sleep(1)
            self.type_text_on_linux_browser(command)
            time.sleep(0.5)
            self.press_enter_button()
            time.sleep(0.5)
            self.press_key_on_linux_browser('F12')
        else:
            raise AssertionError(f'The requested operation is only implemented for windows')

    def is_running(self):
        """Returns True if an instance of the browser is open"""
        if sys.platform == 'win32':
            self.refresh_hwnd_list()
            return bool(self.get_hwnd())
        elif sys.platform == 'linux':
            # Check via xdotool (window present in the current DISPLAY's X server),
            # not pgrep — pgrep would match chrome on a different DISPLAY (e.g. the
            # user's :0 session while we run under xvfb on :100), giving a false
            # positive that makes the caller skip launching our own chrome.
            if not shutil.which('xdotool'):
                # Fallback to pgrep if xdotool missing
                res = _linux_run(['pgrep', '-f', self.linux_binary], timeout=5)
                return bool(res and res.returncode == 0 and (res.stdout or '').strip())
            return bool(_xdotool('search', '--name', self.linux_window_name))
        else:
            return self.app_obj.is_running()

    def press_tab_button(self):
        """Using the keyboard, press the TAB button"""
        if sys.platform == 'win32':
            return self.send_keyboard_keys("{TAB}")
        elif sys.platform == 'linux':
            return self.press_key_on_linux_browser('Tab')
        else:
            return self.press_key_combination_on_mac_browser('key code 48')

    def approve_chrome_changed_assets_alert(self, tab_presses=4):
        """Using the keyboard to click on "keep changes" at chrome's "accept asset change" popup

        :param tab_presses: Number of times to press the tab key before pressing Enter. Set to 4 to support Chrome ver83
        """
        logger.debug(f'Pressing {tab_presses} "tab" an an "enter" to click on "keep changes"')
        for key_press in range(tab_presses):
            self.press_tab_button()
            time.sleep(1)  # Time for the button to register correctly in the OS
        self.press_enter_button()
        time.sleep(1)  # Time for the button to register correctly in the OS

    def open_a_new_tab(self):
        """Press the Ctrl + t combination using keyboard keys to open a new tab"""
        logger.debug('Attempting to open a new tab')
        if sys.platform == 'win32':
            self.send_keyboard_keys('^t')
        elif sys.platform == 'linux':
            self.press_key_on_linux_browser('ctrl+t')
        else:
            self.press_key_combination_on_mac_browser('key code 17 using command down')

    def reset_zoom_level(self):
        """Press the combination ctrl/command + '0' keyboard keys - reset zoom level to 100%"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('^0')
        elif sys.platform == 'linux':
            self.press_key_on_linux_browser('ctrl+0')
        else:
            self.press_key_combination_on_mac_browser('key code 82 using command down')

    def decrease_zoom_level(self):
        """Press the combination ctrl/command + '-' keyboard keys - zoom out"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('^{-}')
        elif sys.platform == 'linux':
            self.press_key_on_linux_browser('ctrl+minus')
        else:
            self.press_key_combination_on_mac_browser('key code 78 using command down')

    def increase_zoom_level(self):
        """Press the combination ctrl/command + '+' keyboard keys - zoom in"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('^{+}')
        elif sys.platform == 'linux':
            self.press_key_on_linux_browser('ctrl+plus')
        else:
            self.press_key_combination_on_mac_browser('key code 69 using command down')

    def set_zoom_level_to_max(self):
        """Press the combination ctrl/command + '+' keyboard keys 10 times - zoom in all the way"""
        self.reset_zoom_level()
        for i in range(10):
            self.increase_zoom_level()

    def set_zoom_level_to_min(self):
        """Press the combination ctrl/command + '-' keyboard keys 10 times - zoom out all the way"""
        self.reset_zoom_level()
        for i in range(10):
            self.decrease_zoom_level()

    def press_page_down(self):
        """Press the page down key"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('{PGDN}')
        elif sys.platform == 'linux':
            self.press_key_on_linux_browser('Next')
        else:
            self.press_key_combination_on_mac_browser('key code 121')

    def press_page_up(self):
        """Press the page up key"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('{PGUP}')
        elif sys.platform == 'linux':
            self.press_key_on_linux_browser('Prior')
        else:
            self.press_key_combination_on_mac_browser('key code 116')

    def press_ctrl_home(self):
        """Press the combination ctrl/command + home keyboard keys - Scroll to top of the page"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('^{HOME}')
        elif sys.platform == 'linux':
            self.press_key_on_linux_browser('ctrl+Home')
        else:
            self.press_key_combination_on_mac_browser('key code 115 using command down')

    def press_ctrl_end(self):
        """Press the combination ctrl/command + end keyboard keys - Scroll to end of the page"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('^{END}')
        elif sys.platform == 'linux':
            self.press_key_on_linux_browser('ctrl+End')
        else:
            self.press_key_combination_on_mac_browser('key code 119 using command down')

    def send_keys_select_all(self):
        """Send keys to "Select all" """
        if sys.platform == 'win32':
            self.send_keyboard_keys('^a')
        elif sys.platform == 'darwin':
            self.press_key_combination_on_mac_browser('key code 0 using command down')
        elif sys.platform == 'linux':
            self.press_key_on_linux_browser('ctrl+a')
        else:
            self.send_keyboard_keys('^a')
