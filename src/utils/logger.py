import sys


class Logger(object):
    """
    将控制台输出同时写入文件。
    """

    def __init__(self, filename="default.log"):
        self.terminal = sys.stdout
        # 使用 'w' 模式，每次运行创建新的日志文件
        self.log = open(filename, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        # 这个 flush 方法是为 Python 3 兼容性所必需的。
        pass
