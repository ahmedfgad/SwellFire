"""GateRunner — auto-runner shooter in Kivy.

M0 stub: minimal Kivy app showing the placeholder menu. Subsequent milestones
(see the plan at /home/ahmed-gad/.claude/plans/) wire up the real screens,
audio, state, and gameplay.
"""

from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition


class PlaceholderMenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_widget(Label(
            text="GateRunner\nM0 skeleton — screens land in M1",
            halign="center",
            valign="middle",
            font_size="32sp",
        ))


class GateRunnerApp(App):
    title = "GateRunner"

    def build(self):
        sm = ScreenManager(transition=FadeTransition(duration=0.25))
        sm.add_widget(PlaceholderMenuScreen(name="menu"))
        return sm


if __name__ == "__main__":
    GateRunnerApp().run()
