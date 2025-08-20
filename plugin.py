import enum
import os
import sys
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import ida_funcs
import ida_idaapi
import ida_kernwin
import ida_lines
import ida_name
import idautils
from imgui_bundle import imgui, imgui_color_text_edit
from imgui_bundle.python_backends import opengl_backend_programmable
from OpenGL import GL

IDAGUI_AUTOSTART = os.environ.get('IDAGUI_AUTOSTART', None) is not None


@contextmanager
def temp_environ(**envvars: Any) -> Any:
    old_env = {k: os.environ.get(k) for k in envvars}
    try:
        os.environ.update({k: str(v) for k, v in envvars.items()})
        yield
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if TYPE_CHECKING:
    from PySide6 import QtCore, QtGui, QtWidgets
else:
    ida_version = tuple(int(v) for v in ida_kernwin.get_kernel_version().split('.'))
    if ida_version >= (9, 2):
        with temp_environ(QT_API='PySide6', FORCE_QT_API='PySide6'):
            from qtpy import QtCore, QtGui, QtWidgets
    else:
        with temp_environ(QT_API='PyQt5', FORCE_QT_API='PyQt5'):
            from qtpy import QtCore, QtGui, QtWidgets


def PLUGIN_ENTRY() -> 'ImGuiPlugin':
    return ImGuiPlugin()


class EventType(enum.Enum):
    MOUSE_PRESS = enum.auto()
    MOUSE_RELEASE = enum.auto()
    MOUSE_MOVE = enum.auto()
    WHEEL = enum.auto()
    KEY_PRESS = enum.auto()
    KEY_RELEASE = enum.auto()
    FOCUS_IN = enum.auto()
    FOCUS_OUT = enum.auto()


def qt_mouse_button_to_imgui(
    button: QtCore.Qt.MouseButton,
) -> imgui.MouseButton_ | None:
    """Convert Qt mouse button codes to ImGui mouse button codes."""
    if button == QtCore.Qt.MouseButton.LeftButton:
        return imgui.MouseButton_.left
    elif button == QtCore.Qt.MouseButton.RightButton:
        return imgui.MouseButton_.right
    elif button == QtCore.Qt.MouseButton.MiddleButton:
        return imgui.MouseButton_.middle
    else:
        print('[WRN] Unknown mouse button:', button, file=sys.stderr)
        return None


def qt_key_to_imgui(key: QtCore.Qt.Key) -> imgui.Key | None:
    """Convert Qt key codes to ImGui key codes."""
    key_map = {
        QtCore.Qt.Key.Key_Tab: imgui.Key.tab,
        QtCore.Qt.Key.Key_Left: imgui.Key.left_arrow,
        QtCore.Qt.Key.Key_Right: imgui.Key.right_arrow,
        QtCore.Qt.Key.Key_Up: imgui.Key.up_arrow,
        QtCore.Qt.Key.Key_Down: imgui.Key.down_arrow,
        QtCore.Qt.Key.Key_PageUp: imgui.Key.page_up,
        QtCore.Qt.Key.Key_PageDown: imgui.Key.page_down,
        QtCore.Qt.Key.Key_Home: imgui.Key.home,
        QtCore.Qt.Key.Key_End: imgui.Key.end,
        QtCore.Qt.Key.Key_Insert: imgui.Key.insert,
        QtCore.Qt.Key.Key_Delete: imgui.Key.delete,
        QtCore.Qt.Key.Key_Backspace: imgui.Key.backspace,
        QtCore.Qt.Key.Key_Space: imgui.Key.space,
        QtCore.Qt.Key.Key_Return: imgui.Key.enter,
        QtCore.Qt.Key.Key_Enter: imgui.Key.enter,
        QtCore.Qt.Key.Key_Escape: imgui.Key.escape,
        QtCore.Qt.Key.Key_A: imgui.Key.a,
        QtCore.Qt.Key.Key_C: imgui.Key.c,
        QtCore.Qt.Key.Key_V: imgui.Key.v,
        QtCore.Qt.Key.Key_X: imgui.Key.x,
        QtCore.Qt.Key.Key_Y: imgui.Key.y,
        QtCore.Qt.Key.Key_Z: imgui.Key.z,
        QtCore.Qt.Key.Key_Control: imgui.Key.left_ctrl,
        QtCore.Qt.Key.Key_Shift: imgui.Key.left_shift,
        QtCore.Qt.Key.Key_Alt: imgui.Key.left_alt,
        QtCore.Qt.Key.Key_Super_L: imgui.Key.left_super,
        QtCore.Qt.Key.Key_Super_R: imgui.Key.right_super,
        QtCore.Qt.Key.Key_Menu: imgui.Key.menu,
        QtCore.Qt.Key.Key_F1: imgui.Key.f1,
        QtCore.Qt.Key.Key_F2: imgui.Key.f2,
        QtCore.Qt.Key.Key_F3: imgui.Key.f3,
        QtCore.Qt.Key.Key_F4: imgui.Key.f4,
        QtCore.Qt.Key.Key_F5: imgui.Key.f5,
        QtCore.Qt.Key.Key_F6: imgui.Key.f6,
        QtCore.Qt.Key.Key_F7: imgui.Key.f7,
        QtCore.Qt.Key.Key_F8: imgui.Key.f8,
        QtCore.Qt.Key.Key_F9: imgui.Key.f9,
        QtCore.Qt.Key.Key_F10: imgui.Key.f10,
        QtCore.Qt.Key.Key_F11: imgui.Key.f11,
        QtCore.Qt.Key.Key_F12: imgui.Key.f12,
    }

    if key in key_map:
        return key_map[key]
    else:
        return None


# --- QWindow subclass: forwards events to handler ---
class ImGuiGLWindow(QtGui.QWindow):
    def __init__(self, parent: Any = None, event_handler: Any = None) -> None:
        super().__init__(parent)
        self.setSurfaceType(QtGui.QWindow.SurfaceType.OpenGLSurface)
        self.event_handler = event_handler

    def mousePressEvent(self, e: Any) -> None:
        if self.event_handler:
            self.event_handler(EventType.MOUSE_PRESS, e)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: Any) -> None:
        if self.event_handler:
            self.event_handler(EventType.MOUSE_RELEASE, e)
        super().mouseReleaseEvent(e)

    def mouseMoveEvent(self, e: Any) -> None:
        if self.event_handler:
            self.event_handler(EventType.MOUSE_MOVE, e)
        super().mouseMoveEvent(e)

    def wheelEvent(self, e: Any) -> None:
        if self.event_handler:
            self.event_handler(EventType.WHEEL, e)
        super().wheelEvent(e)

    def keyPressEvent(self, e: Any) -> None:
        if self.event_handler:
            self.event_handler(EventType.KEY_PRESS, e)
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e: Any) -> None:
        if self.event_handler:
            self.event_handler(EventType.KEY_RELEASE, e)
        super().keyReleaseEvent(e)

    def focusInEvent(self, e: Any) -> None:
        if self.event_handler:
            self.event_handler(EventType.FOCUS_IN, e)
        super().focusInEvent(e)

    def focusOutEvent(self, e: Any) -> None:
        if self.event_handler:
            self.event_handler(EventType.FOCUS_OUT, e)
        super().focusOutEvent(e)


class ImGuiOpenGLWidget(QtWidgets.QWidget):
    def __init__(self, ini_prefix: str, parent: Any = None) -> None:
        super().__init__(parent)

        # GL window
        self.opengl_window = ImGuiGLWindow(event_handler=self.handle_event)

        # GL format
        fmt = QtGui.QSurfaceFormat()
        fmt.setMajorVersion(3)
        fmt.setMinorVersion(3)
        fmt.setProfile(QtGui.QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        self.opengl_window.setFormat(fmt)

        # Wrap window in a container inside this QWidget
        container = QtWidgets.QWidget.createWindowContainer(self.opengl_window, self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(container)

        # GL context
        self.context = QtGui.QOpenGLContext()
        self.context.setFormat(fmt)
        assert self.context.create()

        # ImGui
        self.imgui_context = imgui.create_context()
        self.renderer = None

        # IO stuff
        imgui.set_current_context(self.imgui_context)
        # Set the ini file name
        io = imgui.get_io()
        io.set_ini_filename(f'{ini_prefix}.ini')
        # Set the scaling factor
        device_pixel_ratio = self.devicePixelRatio()
        io.display_framebuffer_scale = imgui.ImVec2(device_pixel_ratio, device_pixel_ratio)

        # Render loop
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.render)
        self.timer.start(16)

    def __del__(self) -> None:
        """Cleanup ImGui context when widget is destroyed."""
        if self.imgui_context:
            imgui.set_current_context(self.imgui_context)
            if self.renderer:
                self.renderer.shutdown()
            imgui.destroy_context(self.imgui_context)

    def handle_event(self, event_type: EventType, event: Any) -> None:
        io = imgui.get_io()
        if event_type == EventType.MOUSE_PRESS:
            button = qt_mouse_button_to_imgui(event.button())
            if button is not None:
                io.add_mouse_button_event(button.value, True)
        elif event_type == EventType.MOUSE_RELEASE:
            button = qt_mouse_button_to_imgui(event.button())
            if button is not None:
                io.add_mouse_button_event(button.value, False)
        elif event_type == EventType.MOUSE_MOVE:
            position = event.position()
            io.add_mouse_pos_event(position.x(), position.y())
        elif event_type == EventType.WHEEL:
            io.add_mouse_wheel_event(0.0, event.angleDelta().y() / 120.0)
        elif event_type == EventType.KEY_PRESS:
            imgui_key = qt_key_to_imgui(event.key())
            if imgui_key is not None:
                io.add_key_event(imgui_key, True)
            if event.text():
                for char in event.text():
                    io.add_input_character(ord(char))
        elif event_type == EventType.KEY_RELEASE:
            imgui_key = qt_key_to_imgui(event.key())
            if imgui_key is not None:
                io.add_key_event(imgui_key, False)
        elif event_type == EventType.FOCUS_IN:
            io.add_focus_event(True)
        elif event_type == EventType.FOCUS_OUT:
            io.add_focus_event(False)

    def render_content(self) -> None:
        """Override this method to render your ImGui content."""
        imgui.show_demo_window()

    def render(self, *args: Any, **kwargs: Any) -> None:
        if not self.opengl_window.isExposed():
            return

        if not self.context.makeCurrent(self.opengl_window):
            return

        if not self.renderer:
            # At this point we should be good to go
            self.renderer = opengl_backend_programmable.ProgrammablePipelineRenderer()

        # Set the current context (for multiple widgets)
        imgui.set_current_context(self.imgui_context)

        size = self.opengl_window.size()
        GL.glViewport(0, 0, size.width(), size.height())
        GL.glClearColor(0.1, 0.1, 0.1, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        io = imgui.get_io()
        io.display_size = imgui.ImVec2(size.width(), size.height())

        try:
            imgui.new_frame()
        except RuntimeError as _:
            # This can happen if something went wrong in the previous frame
            return

        try:
            self.render_content()
        except (RuntimeError, Exception) as _:
            traceback.print_exc()
        finally:
            # Always call render to complete the frame, even if render_content fails
            imgui.render()

        if self.renderer:
            self.renderer.render(imgui.get_draw_data())
        self.context.swapBuffers(self.opengl_window)


def format_label_value(label: str, value: str, alignment: int = 12) -> str:
    return f'{label:<{alignment}}: {value}'


def get_function_disassembly(func_ea: int) -> str | None:
    try:
        funk = ida_funcs.get_func(func_ea)
        if not funk:
            return None

        lines = []
        for address in funk.code_items():
            disasm = ida_lines.generate_disasm_line(address, 0)
            if not disasm:
                continue

            disasm = ida_lines.tag_remove(disasm)
            lines.append(f'{address:08X}  {disasm}')

        return '\n'.join(lines)
    except Exception as _:
        print(traceback.format_exc(), file=sys.stderr)
        return None


@dataclass
class Function:
    name: str
    address: int


class DemoState:
    def __init__(self) -> None:
        self.functions = [
            Function(name=ida_name.get_name(ea), address=ea) for ea in idautils.Functions()
        ]
        self.current_function_index: int | None = None
        self.current_temporary_function_index: int | None = None
        self.filter_text = ''

    def best_function_index(self) -> int | None:
        if self.current_temporary_function_index is not None:
            return self.current_temporary_function_index
        return self.current_function_index


class DemoImGuiWidget(ImGuiOpenGLWidget):
    """Example ImGui widget showing how to subclass ImGuiOpenGLWidget."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.counter = 0
        self.state = DemoState()

        self.editor = imgui_color_text_edit.TextEditor()
        self.editor.set_language_definition(self.editor.LanguageDefinitionId.c)
        self.editor.set_read_only_enabled(True)
        self.editor.set_show_whitespaces_enabled(False)
        self.editor.set_show_line_numbers_enabled(False)

    def render_content(self) -> None:
        """Render ImGui demo content as a fullscreen window."""
        # Get the display size to make the window fullscreen
        io = imgui.get_io()
        display_size = io.display_size

        # Set window to fullscreen with no decorations
        imgui.set_next_window_pos(imgui.ImVec2(0, 0))
        imgui.set_next_window_size(display_size)

        # Window flags for fullscreen: no title bar, no resize, no move, no collapse
        window_flags = (
            imgui.WindowFlags_.no_title_bar.value
            | imgui.WindowFlags_.no_resize.value
            | imgui.WindowFlags_.no_move.value
            | imgui.WindowFlags_.no_collapse.value
            | imgui.WindowFlags_.no_background.value
            | imgui.WindowFlags_.no_bring_to_front_on_focus.value
        )

        imgui.begin('FullscreenWindow', flags=window_flags)

        if imgui.begin_table('Functions:', 2, imgui.TableFlags_.resizable.value):
            imgui.table_setup_column('Functions', imgui.TableColumnFlags_.width_fixed.value, 200.0)
            imgui.table_setup_column('Details', imgui.TableColumnFlags_.width_stretch.value)
            # Left column
            imgui.table_next_column()

            # Filter input
            imgui.set_next_item_width(-1)
            _, self.state.filter_text = imgui.input_text_with_hint(
                '##filter-text', '<filter>', self.state.filter_text
            )
            imgui.set_item_default_focus()

            if imgui.begin_list_box('##functions-list-box', imgui.ImVec2(-1, -1)):
                self.state.current_temporary_function_index = None

                # Filter functions based on the filter text
                filtered_functions = []
                if self.state.filter_text:
                    filter_lower = self.state.filter_text.lower()
                    for i, function in enumerate(self.state.functions):
                        if filter_lower in function.name.lower():
                            filtered_functions.append((i, function))
                else:
                    filtered_functions = list(enumerate(self.state.functions))

                for original_index, function in filtered_functions:
                    is_selected = original_index == self.state.current_function_index
                    clicked, _ = imgui.selectable(f'{function.name}', is_selected)
                    if clicked:
                        self.state.current_function_index = original_index
                        if is_selected:
                            imgui.set_item_default_focus()

                    if imgui.is_item_hovered():
                        self.state.current_temporary_function_index = original_index

                imgui.end_list_box()

            # Right column
            imgui.table_next_column()
            best_function_index = self.state.best_function_index()
            if best_function_index is not None:
                function = self.state.functions[best_function_index]
                imgui.text(format_label_value('Name', function.name))

                # Get demangled name
                demangled_name = ida_name.get_demangled_name(function.address, 0, 0, 0)
                if demangled_name and demangled_name != function.name:
                    imgui.text(format_label_value('Demangled', demangled_name))

                imgui.text(format_label_value('Address', f'{function.address:08X}'))

                # Disassembly section
                imgui.separator()
                disasm_text = get_function_disassembly(function.address)

                self.editor.set_text(disasm_text if disasm_text else '// no disassembly available')
                self.editor.render(
                    '##disasm-text',
                    False,
                    imgui.ImVec2(-1, -1),
                    False,
                )

            imgui.end_table()

        imgui.end()


class ImGuiPluginMainWidget(ida_kernwin.PluginForm):
    APP_NAME: str = 'Function Search [KE]'

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def OnCreate(self, form: Any) -> None:
        widget = self.FormToPyQtWidget(form)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(main_layout)

        imgui_widget = DemoImGuiWidget()
        main_layout.addWidget(imgui_widget, 1)

    def OnClose(self, _form: Any) -> None:
        pass

    def Show(self, *args: Any) -> None:
        super().Show(self.name)


class ImGuiPlugin(ida_idaapi.plugin_t):
    flags = ida_idaapi.PLUGIN_PROC
    comment = 'IDA Pro ImGui Plugin'
    help = ''
    wanted_name = 'ImGui Plugin'
    wanted_hotkey = ''

    counter: int = 0

    def init(self) -> Any:
        def auto_open_gui() -> int:
            self.open_gui()
            return -1  # stop timer

        if IDAGUI_AUTOSTART:
            ida_kernwin.register_timer(0, auto_open_gui)

        return ida_idaapi.PLUGIN_KEEP

    def open_gui(self) -> None:
        main_widget = ImGuiPluginMainWidget(f'ImGui Plugin {self.counter}')
        main_widget.Show()
        self.counter += 1

    def run(self, _arg: Any) -> None:
        self.open_gui()

    def term(self) -> None:
        pass

    def test(self) -> None:
        pass
