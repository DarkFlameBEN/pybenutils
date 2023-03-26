# pybenutils
PyBEN Utilities repository, Contains a variety of useful methods and classes designed to allow easy access to high level operations 

### Installation
Win:
> python -m pip install pybenutils -U

macOS:
> python3 -m pip install pybenutils -U

### AutoGUI module
PyBenAutoGui - Class to automate cross platform GUI interactions.
```
options:                                                                                                                   
  -h, --help            show this help message and exit                                                                    
  -t TITLE, --title TITLE                                                                                                  
                        Window title                                                                                       
  -a APP_PATH, --app_path APP_PATH                                                                                         
                        Application/Exe path                                                                               
  -b PYWINAUTO_BACKEND, --pywinauto_backend PYWINAUTO_BACKEND                                                              
                        A name of used back-end in Windows OS (values: "win32", "uia")                                     
  -c COMMAND, --command COMMAND                                                                                            
                        Function name to execute in the AutoGui Class                                                      
  -eh, --extra_help, --no-extra_help                                                                                       
                        Display extra help about the class and its functions (default: False)

```

> python -m pybenutils.autogui -t "Calculator" -a calc.exe -c get_object_details -b uia

> python3 -m pybenutils.autogui -t "Calculator" -a /Application/Calculator.app -c get_object_details

```
class AutoGui(builtins.object)
 |  AutoGui(title, app_path, pywinauto_backend='uia')
 |  
 |  Methods defined here:
 |  
 |  __init__(self, title, app_path, pywinauto_backend='uia')
 |      Unified interface to interact with Gui Elements
 |      
 |      :param title: Window title
 |      :param app_path: Application/Exe path
 |      :param pywinauto_backend: A name of used back-end in Windows OS (values: "win32", "uia")
 |  
 |  click_on_text(self, text: str)
 |      Clicks on text object location using pyautogui
 |  
 |  find_objects(self, text='', control_type='')
 |      Returns an iterable containing the matching object
 |      
 |      :param text: Text to search, In windows can also be the automation_id
 |      :param control_type: Filter by control type
 |      :return: An iterable containing the matching object
 |  
 |  focus_on_window(self)
 |      Focus on the app window - bring to front
 |  
 |  get_object_details(self, text='', control_type='')
 |      Returns an iterable containing dicts of matching objects properties
 |      
 |      :param text: Text to search, In windows can also be the automation_id
 |      :param control_type: Filter by control type
 |      :return: An iterable containing dicts of matching objects properties
 |  
 |  get_object_position_by_text(self, text)
 |      Return position as tuple (xl, yt, xr, yb) in windows / (x, y) in mac
```
