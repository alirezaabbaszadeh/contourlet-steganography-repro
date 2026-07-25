import unittest

import numpy as np

from ctsteg.encryption import (
    decrypt_secret,
    encrypt_secret,
    pseudocode_reachability,
)


class EncryptionTests(unittest.TestCase):
    def test_interpreted_mapping_round_trip(self) -> None:
        rng = np.random.default_rng(17)
        source = rng.integers(0, 256, size=(32, 32)).astype(np.float64)
        encrypted = encrypt_secret(source, mode="interpreted")
        recovered = decrypt_secret(encrypted, stabilize_hp=False)
        np.testing.assert_allclose(recovered, source, atol=1e-9)

    def test_strict_mapping_exposes_undefined_hp_branch(self) -> None:
        source = np.full((8, 8), 200.0)
        with self.assertRaisesRegex(ValueError, "CODE_HP undefined"):
            encrypt_secret(source, mode="strict")

    def test_ap_high_branch_is_unreachable(self) -> None:
        facts = pseudocode_reachability()
        self.assertTrue(facts["l1_equals_l2_on_uint8_domain"])
        self.assertFalse(facts["ap_high_branch_reachable_after_not_in_l1"])


if __name__ == "__main__":
    unittest.main()

