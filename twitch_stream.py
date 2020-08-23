import queue
import sys

import ffmpeg
import sounddevice as sd
import streamlink

twitch_id = "gothamchess"

streams = streamlink.streams(f"https://twitch.tv/{twitch_id}")

print(f"Streams: {list(streams.keys())}")

stream = streams['audio_only']
print(f"URL: {stream.url}")

stream_info = ffmpeg.probe(stream.url, cmd=r'ffmpeg\ffprobe.exe')
print(f"{stream_info=}")


audio_streams = [_stream for _stream in stream_info['streams'] if _stream.get('codec_type') == 'audio']
assert len(audio_streams) == 1, f"{len(audio_streams)} stream found."

audio_stream = audio_streams[0]
print(f"{audio_stream=}")

stream_codec_type = audio_stream.get('codec_type')
assert stream_codec_type == 'audio', f"Stream must be audio, not {stream_codec_type}"

channels = audio_stream['channels']
samplerate = float(audio_stream['sample_rate'])

buffersize = 20  # Number of blocks used for buffering
blocksize = 1024  # Block size
q = queue.Queue(maxsize=buffersize)


def callback(outdata, frames, time, status):
    assert frames == blocksize
    if status.output_underflow:
        print('Output underflow: increase blocksize?', file=sys.stderr)
        raise sd.CallbackAbort
    assert not status
    try:
        data = q.get_nowait()
    except queue.Empty:
        print('Buffer is empty: increase buffersize?', file=sys.stderr)
        raise sd.CallbackAbort
    assert len(data) == len(outdata)
    outdata[:] = data


try:
    print('Opening stream.')
    process = ffmpeg.input(
        stream.url
    ).output(
        'pipe:',
        format='f32le',
        acodec='pcm_f32le',
        ac=channels,
        ar=samplerate,
        loglevel='quiet',
    ).run_async(pipe_stdout=True)
    output_stream = sd.RawOutputStream(
        samplerate=samplerate, blocksize=blocksize,
        # device=device,
        channels=channels, dtype='float32',
        callback=callback
    )
    read_size = blocksize * channels * output_stream.samplesize
    print(output_stream.samplesize)
    print('Buffering.')
    for _ in range(buffersize):
        q.put_nowait(process.stdout.read(read_size))
    print('Starting playback.')
    with output_stream:
        timeout = blocksize * buffersize / samplerate * 2  # 2 for extra buffer? idk?
        while True:
            q.put(process.stdout.read(read_size), timeout=timeout)
except KeyboardInterrupt:
    print('\nInterrupted by user')
# except queue.Full:
#     # A timeout occurred, i.e. there was an error in the callback
#     print("Queue full?")
except Exception as e:
    import traceback
    traceback.print_exc()


# while True:
#     stream_data = np.frombuffer(fd.read(12*44100), dtype=np.int16)
#     sd.play(stream_data)
#     sd.sleep(1000)
