"""
游戏入口：python -m ui 或安装后执行 gei-world。
"""


def main():
    from ui.client_controller import UIClient

    UIClient().run()


if __name__ == "__main__":
    main()
