from oblivion.certificate import Ed25519SignerVerifier
from oblivion.core.hashing import Hasher


def test_hasher(tmp_path):
    # File hashing.
    #
    # Written into pytest's tmp_path rather than the working directory. This
    # test previously wrote `test_file.txt` beside whatever directory pytest was
    # invoked from and never removed it, so every run left an untracked file in
    # the repository root. The assertions are unchanged; only the location is.
    target = tmp_path / "test_file.txt"
    target.write_text("hello", encoding="utf-8")

    h1 = Hasher.hash_file(target)
    h2 = Hasher.hash_file(target)

    assert h1 == h2
    assert len(h1) == 64

    # Data hashing
    d1 = {"a": 1, "b": 2}
    d2 = {"b": 2, "a": 1}
    assert Hasher.hash_data(d1) == Hasher.hash_data(d2)

def test_signer_verifier():
    signer = Ed25519SignerVerifier.generate()
    data = b"evidence_data"
    signature = signer.sign(data)

    public_key = signer.get_public_key_bytes()

    assert Ed25519SignerVerifier.verify(public_key, data, signature)
    assert not Ed25519SignerVerifier.verify(public_key, b"wrong_data", signature)

    # Test tampering
    tampered_signature = signature[:-1] + b"x"
    assert not Ed25519SignerVerifier.verify(public_key, data, tampered_signature)
