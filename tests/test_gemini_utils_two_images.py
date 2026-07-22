import json
from unittest.mock import MagicMock, patch

import PIL.Image

from app import gemini_utils, config


def _make_test_image(color):
    return PIL.Image.new("RGB", (10, 10), color=color)


def test_generate_json_from_two_images_sends_both_images_in_one_call():
    front_img = _make_test_image("white")
    back_img = _make_test_image("black")
    fake_response = MagicMock()
    fake_response.text = json.dumps({
        "name": "王大明 David Wang",
        "title": "工程師",
        "company": "科技公司",
        "address": "台北市",
        "phone": "#886-02-1234-5678",
        "email": "david@example.com"
    })

    with patch.object(gemini_utils, "GenerativeModel") as mock_model_cls:
        mock_model = mock_model_cls.return_value
        mock_model.generate_content.return_value = fake_response

        result = gemini_utils.generate_json_from_two_images(
            front_img, back_img, config.DOUBLE_SIDED_IMAGE_PROMPT
        )

        assert result is fake_response
        mock_model_cls.assert_called_once_with(
            "gemini-3-flash-preview",
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": gemini_utils.NAMECARD_SCHEMA
            },
        )
        call_args = mock_model.generate_content.call_args
        contents = call_args.args[0]
        assert contents[0] == config.DOUBLE_SIDED_IMAGE_PROMPT
        assert len(contents) == 3
        assert call_args.kwargs["stream"] is False
        assert call_args.kwargs["labels"] == {"client_id": "namecard"}
