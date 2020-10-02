import time
from pynput.mouse import Button, Controller


def mouse_click_on_point(x_position, y_position):
    """moves the mouse corsair to the wanted position and clicking on it

    :param x_position: x position
    :param y_position: y position
    :return:
    """
    mouse = Controller()

    # Read pointer position
    print('The current pointer position is {0}'.format(mouse.position))

    # Set pointer position
    mouse.position = (x_position, y_position)
    print('Now we have moved it to {0}'.format(mouse.position))

    # Move pointer relative to current position
    mouse.move(5, -5)

    # Press and release
    mouse.press(Button.left)
    mouse.release(Button.left)

    # Double click; this is different from pressing and releasing
    # twice on Mac OSX
    mouse.click(Button.left, 2)

    # Scroll two steps down
    mouse.scroll(0, 2)


def mouse_drag(initial_x_pos, initial_y_pos, final_x_pos, final_y_pos):
    """Dragging an object from initial position to its final position

    :param initial_x_pos: Initial x position
    :param initial_y_pos: Initial y position
    :param final_x_pos: Final x position
    :param final_y_pos: Final y position
    """
    mouse = Controller()
    mouse.position = (initial_x_pos, initial_y_pos)
    mouse.press(Button.left)
    mouse.move(final_x_pos - initial_x_pos, final_y_pos - initial_y_pos)
    time.sleep(1)
    mouse.release(Button.left)
