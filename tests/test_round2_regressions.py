import unittest

from server.app import resolve_client_id


class TrustedProxyClientIdTests(unittest.TestCase):
    def test_uses_last_forwarded_for_entry_when_proxy_is_trusted(self):
        self.assertEqual(
            resolve_client_id("127.0.0.1", "6.6.6.6, 100.64.0.5", True),
            "100.64.0.5",
        )

    def test_single_forwarded_entry_is_accepted(self):
        self.assertEqual(resolve_client_id("127.0.0.1", "100.64.0.5", True), "100.64.0.5")

    def test_forwarded_header_is_ignored_without_trusted_proxy(self):
        self.assertEqual(resolve_client_id("127.0.0.1", "100.64.0.5", False), "127.0.0.1")

    def test_forwarded_header_is_ignored_for_non_loopback_peer(self):
        self.assertEqual(resolve_client_id("192.0.2.10", "100.64.0.5", True), "192.0.2.10")


if __name__ == "__main__":
    unittest.main()
