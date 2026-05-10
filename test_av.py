import av
print(f"PyAV version: {av.__version__}")

import numpy as np

import av, numpy as np, io

# Test: use resampler output frames directly for encoding
container = av.open(r"F:\屏幕录制\bandicam 2026-05-07 20-04-21-162.mp4")
ast = container.streams.audio[0]
duration = float(container.duration) / float(av.time_base)
print(f"Duration: {duration:.1f}s, Audio: {ast.codec_context.name}, {ast.rate}Hz, layout={ast.layout.name}")

# Resampler: any format -> 16kHz mono flt
resampler = av.audio.resampler.AudioResampler(format='fltp', layout='mono', rate=16000)

# Write to BytesIO
out_io = io.BytesIO()
out = av.open(out_io, 'w', format='wav')
out_s = out.add_stream('pcm_s16le', 16000)

total = 0; limit = 16000 * 5  # 5 seconds
count = 0

for frame in container.decode(ast):
    pts = float(frame.pts) * float(ast.time_base)
    if pts > 5.2:
        break
    if pts < 0:
        continue
    for rf in resampler.resample(frame):
        # rf is already flt format
        print(f"  Resampled frame: {rf.samples} samples, format={rf.format.name}, layout={rf.layout.name}")
        # Directly encode the resampled frame!
        for pkt in out_s.encode(rf):
            out.mux(pkt)
        total += rf.samples
        count += 1
        print(f"  Encoded OK. total={total}, count={count}")
        if total >= limit:
            break
    if total >= limit:
        break

for pkt in out_s.encode(None):
    out.mux(pkt)
out.close()
container.close()

out_io.seek(0)
wav_data = out_io.read()
print(f"WAV size: {len(wav_data)} bytes (expected ~{limit*2} for 5s of s16 mono)")
print("SUCCESS!")

# Test extracting first 5s from the video
container = av.open(r"F:\屏幕录制\bandicam 2026-05-07 20-04-21-162.mp4")
ast = container.streams.audio[0]
print(f"Audio stream: {ast.codec_context.name}, {ast.rate}Hz, {ast.layout.name}")
print(f"Duration: {float(container.duration) / float(av.time_base):.1f}s")
container.close()
print("All tests passed!")