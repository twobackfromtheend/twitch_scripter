import collections
import logging
import queue
import time

import numpy as np
import webrtcvad
from scipy import signal

logger = logging.getLogger(__name__)


class VadSegmenter:
    def __init__(self, aggressiveness: int = 3):
        self.vad = webrtcvad.Vad(aggressiveness)

    def segmenter(
            self, q: queue.Queue,
            block_size: int, sample_rate: int, padding_ms: int = 300,
            ratio: float = 0.75,
    ):
        """

        :param q:
        :param block_size:
        :param sample_rate:
        :param padding_ms:
            Number of milliseconds desired in padding.
            Effective padding duration = (1 - ratio) * padding_ms ?
            TODO: check
        :param ratio:
            Minimum fraction of padding_ms that has to be voiced/non-voice to activate.
        :return:
        """
        frame_duration_ms = 1000 * block_size / sample_rate
        num_padding_frames = int(padding_ms / frame_duration_ms)
        ring_buffer = collections.deque(maxlen=num_padding_frames)
        triggered = False

        while True:
            try:
                data = q.get(timeout=5)
                # data = q.get_nowait()
            except queue.Empty:
                logger.warning('Buffer is empty: increase buffersize?')
                time.sleep(1)
                continue
            frame = data
            if len(frame) < 640:
                return

            assert webrtcvad.valid_rate_and_frame_length(sample_rate, int(
                len(frame) / 2)), "WebRTC VAD only supports frames that are 10, 20, or 30 ms long"

            is_speech = self.vad.is_speech(frame, sample_rate)

            if not triggered:
                ring_buffer.append((frame, is_speech))
                num_voiced = len([f for f, is_speech in ring_buffer if is_speech])
                # TODO: replace with sum?
                if num_voiced > ratio * ring_buffer.maxlen:
                    triggered = True
                    for f, s in ring_buffer:
                        yield f
                    ring_buffer.clear()

            else:
                yield frame
                ring_buffer.append((frame, is_speech))
                num_unvoiced = len([f for f, is_speech in ring_buffer if not is_speech])
                # TODO: replace with sum?
                if num_unvoiced > ratio * ring_buffer.maxlen:
                    triggered = False
                    yield None
                    ring_buffer.clear()


def resample(data, resample_factor: float):
    """
    Resamples audio by desired factor.
    :param data: Binary data
    :param resample_factor: output rate / input rate
    :return:
    """
    data16 = np.frombuffer(data, dtype=np.float32)
    resample_size = int(len(data16) * resample_factor)
    resample = signal.resample(data16, resample_size)
    resample16 = np.array(resample, dtype=np.int16)
    return resample16.tostring()
