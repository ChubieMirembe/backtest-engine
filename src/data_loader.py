from itch.parser import MessageParser


class ITCHDataLoader:
    def __init__(self, file_path: str, message_types: bytes):
        self.file_path = file_path
        self.parser = MessageParser(message_type=message_types)

    def stream_messages(self):
        with open(self.file_path, "rb") as f:
            for msg in self.parser.parse_file(f):
                yield msg, msg.decode()