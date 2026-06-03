"""
UI 弹窗输入框测试。
"""

import pygame

from ui.systems.ui_system import UISystem


def test_modal_text_inputs_edit_and_collect_values():
    pygame.init()
    ui = UISystem(800, 600)
    ui.show_modal(
        "输入测试",
        ["填写字段"],
        [],
        inputs=[
            {"key": "url", "label": "地址", "value": "http://"},
            {"key": "room", "label": "房间", "value": ""},
        ]
    )

    assert ui.handle_text_input("x")
    assert ui.get_modal_input_values()["url"] == "http://x"
    assert ui.handle_key_press(pygame.K_TAB)
    assert ui.handle_text_input("r")
    assert ui.get_modal_input_values()["room"] == "r"
    assert ui.handle_key_press(pygame.K_BACKSPACE)
    assert ui.get_modal_input_values()["room"] == ""
    assert ui.set_modal_input_value("room", "room_1")
    assert ui.get_modal_input_values()["room"] == "room_1"


def test_modal_without_inputs_ignores_text_input():
    pygame.init()
    ui = UISystem(800, 600)
    ui.show_modal("普通弹窗", ["无输入"], [])
    assert not ui.handle_text_input("x")
    assert not ui.handle_key_press(pygame.K_BACKSPACE)
