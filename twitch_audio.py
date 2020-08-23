import logging
import queue

import ffmpeg
import streamlink

logger = logging.getLogger(__name__)


class TwitchAudio:
    def __init__(
            self,
            twitch_id: str,
            buffer_size: int,
            block_size: int,
            channels: int = None,
            sample_rate: int = None,
    ):
        """

        :param twitch_id:
        :param buffer_size: Number of blocks used for buffering
        :param block_size: Block size
        """
        self.twitch_id = twitch_id
        streams = streamlink.streams(f"https://twitch.tv/{twitch_id}")
        logging.info(f"streamlink.streams keys: {list(streams.keys())}")

        self.audio_stream_url = streams['audio_only'].url
        logging.info(f"{self.audio_stream_url=}")
        stream_info = ffmpeg.probe(self.audio_stream_url, cmd=r'ffmpeg\ffprobe.exe')
        logging.info(f"{stream_info=}")

        audio_streams = [_stream for _stream in stream_info['streams'] if _stream.get('codec_type') == 'audio']
        if len(audio_streams) != 1:
            raise ValueError(f"{len(audio_streams)} audio streams found (expected 1).")

        audio_stream = audio_streams[0]
        logging.info(f"{audio_stream=}")

        self.channels = audio_stream['channels'] if channels is None else channels
        self.sample_rate = int(audio_stream['sample_rate']) if sample_rate is None else sample_rate

        self.buffer_size = buffer_size
        self.block_size = block_size

        self.read_size = self.block_size * self.channels * 2  # s16 is 2 bytes

    def connect(self, q: queue.Queue):
        process = ffmpeg.input(self.audio_stream_url).output(
            'pipe:',
            # format='f32le',
            # acodec='pcm_f32le'
            format='s16le',
            acodec='pcm_s16le',
            ac=self.channels,
            ar=self.sample_rate,
            loglevel='quiet',
        ).run_async(pipe_stdout=True)

        logger.info('Buffering.')
        for _ in range(self.buffer_size):
            q.put_nowait(process.stdout.read(self.read_size))
        logger.info('Completed buffering.')
        return process


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # buffer_size = 20
    # block_size = 2000
    buffer_size = 100
    block_size = 480
    channels = 1
    sample_rate = 16000
    audio = TwitchAudio('gothamchess', buffer_size, block_size, channels, sample_rate)
    q = queue.Queue(maxsize=buffer_size)
    import sys
    import sounddevice as sd


    def callback(outdata, frames, time, status):
        if status.output_underflow:
            print('Output underflow: increase block_size?', file=sys.stderr)
            raise sd.CallbackAbort
        assert not status
        try:
            # data = q.get_nowait()
            data = q.get(timeout=1)
        except queue.Empty:
            print('Buffer is empty: increase buffersize?', file=sys.stderr)
            raise sd.CallbackAbort
        assert len(data) == len(outdata), f"{len(data)}, {len(outdata)}"
        outdata[:] = data


    output_stream = sd.RawOutputStream(
        samplerate=audio.sample_rate, blocksize=block_size,
        # device=device,
        channels=1, dtype='int16',
        callback=callback
    )
    process = audio.connect(q)
    with output_stream:
        timeout = block_size * buffer_size / audio.sample_rate  # 2 for extra buffer? idk?
        while True:
            q.put(process.stdout.read(audio.read_size), timeout=timeout)
