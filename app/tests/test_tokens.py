from app.services.claim import can_transition
from app.utils.tokens import (
    SHORT_CODE_ALPHABET,
    TokenKind,
    format_short_code,
    new_short_code,
    new_token,
    normalize_short_code,
    token_kind,
)


class TestTokens:
    def test_tokens_have_prefix_and_length(self):
        for kind in TokenKind:
            token = new_token(kind)
            assert token.startswith(f"{kind.value}_")
            assert len(token) == 24
            assert token_kind(token) is kind

    def test_tokens_are_unique(self):
        assert len({new_token(TokenKind.CLAIM) for _ in range(1000)}) == 1000

    def test_token_kind_rejects_garbage(self):
        assert token_kind("x_" + "a" * 22) is None
        assert token_kind("c_short") is None
        assert token_kind("nounderscore") is None


class TestShortCodes:
    def test_alphabet_and_format(self):
        code = new_short_code()
        assert len(code) == 6
        assert set(code) <= set(SHORT_CODE_ALPHABET)
        assert format_short_code("K7F2QX") == "K7F-2QX"

    def test_normalize_forgives_typing(self):
        assert normalize_short_code("k7f-2qx") == "K7F2QX"
        assert normalize_short_code(" o1l 2ab ") == "0112AB"


class TestClaimTransitions:
    def test_allowed(self):
        assert can_transition("CREATED", "STORED")
        assert can_transition("STORED", "RETURNED")
        assert can_transition("STORED", "UNCLAIMED")
        assert can_transition("UNCLAIMED", "RETURNED")

    def test_final_states_are_final(self):
        for target in ("CREATED", "STORED", "RETURNED", "UNCLAIMED", "VOID"):
            assert not can_transition("RETURNED", target)
            assert not can_transition("VOID", target)

    def test_cannot_skip_drop_off(self):
        assert not can_transition("CREATED", "RETURNED")
