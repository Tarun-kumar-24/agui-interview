import unittest

from fastapi import HTTPException

import main


class EdgeTtsEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_streams_only_audio_chunks(self):
        calls = {}
        original_communicate = main.edge_tts.Communicate

        class FakeCommunicate:
            def __init__(self, text, voice, rate, volume):
                calls.update(text=text, voice=voice, rate=rate, volume=volume)

            async def stream(self):
                yield {"type": "metadata", "data": b"ignored"}
                yield {"type": "audio", "data": b"first"}
                yield {"type": "audio", "data": b"second"}

        main.edge_tts.Communicate = FakeCommunicate
        try:
            response = await main.synthesize_speech(
                main.TTSRequest(text="  Hello   candidate.  ")
            )
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
        finally:
            main.edge_tts.Communicate = original_communicate

        self.assertEqual(b"".join(chunks), b"firstsecond")
        self.assertEqual(response.media_type, "audio/mpeg")
        self.assertEqual(calls["text"], "Hello candidate.")
        self.assertEqual(calls["voice"], main.EDGE_TTS_VOICE)

    async def test_rejects_unapproved_voice(self):
        with self.assertRaises(HTTPException) as raised:
            await main.synthesize_speech(
                main.TTSRequest(text="Hello", voice="unsupported-voice")
            )

        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
