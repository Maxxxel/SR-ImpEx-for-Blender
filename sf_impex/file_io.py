class FileReader:
    def __init__(self, file_name: str):
        self.file = open(file_name, 'rb')

    def read(self, size: int):
        return self.file.read(size)

    def seek(self, offset: int):
        self.file.seek(offset)

    def close(self):
        self.file.close()

    def tell(self):
        return self.file.tell()


class FileWriter:
    def __init__(self, file_name: str):
        self.file = open(file_name, 'wb')

    def write(self, data: bytes):
        self.file.write(data)

    def close(self):
        self.file.close()

    def tell(self):
        return self.file.tell()
