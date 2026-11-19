import json

from liveslide_model.publish.api_client import publish_batches


def test_dry_run_writes_batches_and_sends_nothing(tmp_path):
    rows = [{"cell_id": str(index)} for index in range(5)]
    count = publish_batches("scores", rows, dry_run=True, output_dir=tmp_path, batch_size=2)
    assert count == 5
    files = sorted(tmp_path.glob("*.json"))
    assert len(files) == 3
    assert sum(len(json.loads(path.read_text())) for path in files) == 5
