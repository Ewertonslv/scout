from core.bedrock import BedrockClient, _parse_json
from core.budget import TokenBudget


class _StubRuntime:
    """Mimics bedrock-runtime.converse()."""

    def __init__(self, text):
        self._text = text

    def converse(self, **_kwargs):
        return {
            "output": {"message": {"content": [{"text": self._text}]}},
            "usage": {"inputTokens": 30, "outputTokens": 70},
        }


def test_parse_json_strips_fences():
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json('{"b": 2}') == {"b": 2}


def test_converse_charges_budget():
    client = BedrockClient(runtime=_StubRuntime("hello"))
    b = TokenBudget()
    reply = client.converse(system="s", user="u", budget=b)
    assert reply.text == "hello"
    assert b.used == 100  # 30 + 70


def test_converse_json_parses():
    client = BedrockClient(runtime=_StubRuntime('{"subtasks": []}'))
    data, reply = client.converse_json(system="s", user="u")
    assert data == {"subtasks": []}
    assert reply.input_tokens == 30
