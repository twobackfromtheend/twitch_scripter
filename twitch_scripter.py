import logging
import queue
import threading
from typing import Callable

import numpy as np
from deepspeech import Model
from halo import Halo

from main import pbmm_path, scorer_path
from twitch_audio import TwitchAudio
from vad import VadSegmenter

logger = logging.getLogger(__name__)


class TwitchScripter:
    buffer_size = 100
    block_size = 480
    channels = 1
    sample_rate = 16000

    def __init__(self, stream_id: str):
        self.audio = TwitchAudio(
            stream_id,
            self.buffer_size, self.block_size, self.channels, self.sample_rate
        )
        self.q = queue.Queue(maxsize=self.buffer_size)

        self.spinner = Halo(
            text='Calculating...',
            spinner='line',
        )

    def start(self, vad_aggressiveness: int = 3, callback: Callable[[str], None] = None):
        process = self.audio.connect(self.q)

        def read_audio():
            timeout = self.block_size * self.buffer_size / self.audio.sample_rate  # 2 for extra buffer? idk?
            while True:
                self.q.put(process.stdout.read(self.audio.read_size), timeout=timeout)

        read_audio_thread = threading.Thread(target=read_audio, daemon=True)
        read_audio_thread.start()

        ds_model = Model(str(pbmm_path))
        ds_model.enableExternalScorer(str(scorer_path))
        stream_context = ds_model.createStream()

        vad_segmenter = VadSegmenter(vad_aggressiveness)
        previous_frame = None
        for frame in vad_segmenter.segmenter(
                self.q,
                block_size=self.block_size, sample_rate=self.sample_rate,
        ):
            if frame is not None:
                self.spinner.start()
                logger.debug("streaming frame")
                stream_context.feedAudioContent(np.frombuffer(frame, np.int16))
            else:
                self.spinner.stop()
                logger.debug("end utterence")

                text = stream_context.finishStream()
                logger.info(f"{text=}")
                if callback:
                    callback(text)
                else:
                    print("Recognized: %s" % text)
                stream_context = ds_model.createStream()
            if (frame is None) != (previous_frame is None):
                logger.info("Streaming frame" if frame is not None else "End utterence")
                previous_frame = frame


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    twitch_scripter = TwitchScripter('gothamchess')
    twitch_scripter.start(vad_aggressiveness=1, callback=lambda x: print(f"Decoded: {x}"))
