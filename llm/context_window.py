import tiktoken


def count_tokens(text: str, model: str = 'gpt-4o-mini') -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


def truncate_to_limit(messages: list[dict], max_tokens: int = 8192, model: str = 'gpt-4o-mini') -> list[dict]:
    total = 0
    truncated = []
    for msg in reversed(messages):
        tokens = count_tokens(msg.get('content', ''), model) + 10
        if total + tokens > max_tokens:
            break
        total += tokens
        truncated.insert(0, msg)
    return truncated


def estimate_cost(tokens: int, model: str = 'gpt-4o-mini') -> float:
    rates = {
        'gpt-4o-mini': (0.15, 0.60),
        'gpt-4o': (2.50, 10.00),
        'claude-3-haiku-20240307': (0.25, 1.25),
        'claude-3-sonnet-20240229': (3.00, 15.00),
    }
    input_rate, output_rate = rates.get(model, (0.50, 1.50))
    return (tokens / 1_000_000) * input_rate
