import asyncio

from companion_worker import execute_tool


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


def run_execute(payload, monkeypatch):
    monkeypatch.setattr("companion_worker.guard", lambda *args, **kwargs: None)
    response = asyncio.run(execute_tool(FakeRequest(payload)))
    return response.body.decode("utf-8")


def test_move_file_moves_to_client_destination(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    destination = tmp_path / "moved.txt"
    source.write_text("hello", encoding="utf-8")

    body = run_execute({
        "tool": "move_file",
        "args": {"source_path": str(source), "destination_path": str(destination)},
    }, monkeypatch)

    assert "Successfully moved" in body
    assert destination.read_text(encoding="utf-8") == "hello"
    assert not source.exists()


def test_organize_folder_sorts_files_on_client(tmp_path, monkeypatch):
    image = tmp_path / "photo.png"
    document = tmp_path / "notes.txt"
    image.write_text("image", encoding="utf-8")
    document.write_text("doc", encoding="utf-8")

    body = run_execute({
        "tool": "organize_folder",
        "args": {"folder_path": str(tmp_path)},
    }, monkeypatch)

    assert "Successfully organized 2 files" in body
    assert (tmp_path / "Images" / "photo.png").exists()
    assert (tmp_path / "Documents" / "notes.txt").exists()
