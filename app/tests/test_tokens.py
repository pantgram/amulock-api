import pytest

from app.utils import contact
from app.utils.tokens import TokenKind, new_token, token_kind


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


class TestContacts:
    def test_phone_normalization(self):
        assert contact.normalize("phone", "+30 691 234-5678") == "+306912345678"
        assert contact.normalize("phone", "0030 6912345678") == "+306912345678"

    def test_email_normalization(self):
        assert contact.normalize("email", "  Maria@Example.COM ") == "maria@example.com"

    @pytest.mark.parametrize(("kind", "value"), [("phone", "6912345678"), ("phone", "+30abc"), ("email", "nope")])
    def test_rejects_invalid(self, kind, value):
        with pytest.raises(ValueError):
            contact.normalize(kind, value)

    def test_encryption_round_trip(self):
        ciphertext = contact.encrypt("+306912345678")
        assert b"6912345678" not in ciphertext
        assert contact.decrypt(ciphertext) == "+306912345678"

    def test_hash_is_stable_and_keyed(self):
        assert contact.hash_contact("a@b.co") == contact.hash_contact("a@b.co")
        assert contact.hash_contact("a@b.co") != contact.hash_contact("c@b.co")
        assert len(contact.hash_contact("a@b.co")) == 32

    def test_mask(self):
        assert contact.mask("phone", "+306912345678") == "+30" + "•" * 6 + "5678"
        assert contact.mask("email", "maria@example.com") == "m•••@example.com"
