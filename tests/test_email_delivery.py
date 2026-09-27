import os
import unittest
from unittest.mock import patch

from controller.routes import send_verification_email


class TestEmailDelivery(unittest.TestCase):
    def setUp(self):
        for key in [
            'EMAIL_PROVIDER',
            'RESEND_API_KEY', 'RESEND_FROM',
            'MAILGUN_API_KEY', 'MAILGUN_DOMAIN',
            'SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME', 'SMTP_USER',
            'SMTP_PASSWORD', 'SMTP_USE_TLS', 'SMTP_USE_SSL', 'SMTP_MOCK',
        ]:
            os.environ.pop(key, None)

    @patch('controller.routes.requests.post')
    def test_send_verification_email_uses_http_api(self, mock_post):
        os.environ['EMAIL_PROVIDER'] = 'resend'
        os.environ['RESEND_API_KEY'] = 'test-key'
        os.environ['RESEND_FROM'] = 'no-reply@example.com'

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'id': 'email_123'}

        result = send_verification_email('usuario@example.com', '123456')

        self.assertTrue(result)
        mock_post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
