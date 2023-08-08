import datetime
import multiprocessing
import os
import time
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import namedtuple
from queue import Empty

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

File = namedtuple('File', ['filename', 'date'])
Job = namedtuple('Job', ['file', 'ratio', 'num', 'results'])


def __proc_job(j: Job):
    try:
        im_pil = Image.open(j.file.filename)
        im_pil.thumbnail((im_pil.size[0] // j.ratio, im_pil.size[1] // j.ratio), Image.HAMMING)
        im_pil = im_pil.rotate(270, expand=True)
        d = ImageDraw.Draw(im_pil)
        font_size = im_pil.size[0] // 20
        stroke_width = font_size // 8
        text_offset = stroke_width * 2
        font = ImageFont.FreeTypeFont('font.otf', size=font_size)
        d.text((text_offset, text_offset), f'{j.num:03d} ' + j.file.date.strftime('%Y/%m/%d %H:%M:%S'),
               fill='white', font=font, stroke_width=stroke_width, stroke_fill='black')
        nd = np.array(im_pil)
        j.results.put((j.num, nd))
    except Exception as e:
        print(e)
        raise e


def timelapse(photos_dir, output, days, fps, resize_ratio, codec_opt=23, procs=os.cpu_count() - 1,
              progress_callback=None, progress_period=1):
    filenames = os.listdir(photos_dir)
    dates = [datetime.datetime.strptime(f[:15], '%Y%m%d_%H%M%S') for f in filenames]
    files = sorted([File(photos_dir + os.sep + f, d) for f, d in zip(filenames, dates)], key=lambda f: f.date)
    min_date = datetime.datetime.now() - datetime.timedelta(days=days)

    filtered = [f for f in files if min_date < f.date]
    if not filtered:
        raise ValueError('Photos not found')

    container = av.open(output, mode='w')
    stream = container.add_stream('h264', rate=fps)
    stream.thread_type = 'AUTO'
    stream.pix_fmt = 'yuv420p'
    stream.options['crf'] = str(codec_opt)

    manager = multiprocessing.Manager()
    results = manager.Queue()
    jobs = [Job(f, resize_ratio, n, results) for n, f in enumerate(filtered)]
    with multiprocessing.Pool(procs) as pool:
        ar = pool.map_async(__proc_job, jobs, chunksize=4)
        next_num = 0
        done_num = 0
        buf = {}
        last_prog = time.time()
        while True:
            if next_num in buf:
                im = buf[next_num]
                del buf[next_num]
                if next_num == 0:
                    stream.height, stream.width = im.shape[:2]

                for packet in stream.encode(av.VideoFrame.from_ndarray(im, format='rgb24')):
                    container.mux(packet)

                next_num += 1
                if next_num == len(jobs):
                    break
            else:
                try:
                    res = results.get(True, 1)
                    done_num += 1
                    n, im = res
                    buf[n] = im
                except Empty:
                    pass
            if ar.ready():
                if not ar.successful():
                    raise RuntimeError('Pool error')
            if progress_callback is not None:
                now = time.time()
                if now - last_prog >= progress_period:
                    last_prog = now
                    progress_callback(done_num * 100 / len(jobs))

        for packet in stream.encode():
            container.mux(packet)
        container.close()
        ar.wait()


if __name__ == '__main__':
    argparser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    argparser.add_argument('-p', '--progress-period', metavar='SECS', default=1, type=int, help='progress print period')
    argparser.add_argument('-r', '--resize-ratio', metavar='RATIO', default=4, type=int, help='downscale ratio')
    argparser.add_argument('-c', '--codec-opt', metavar='OPT', default=23, type=int, help='x264 crf')
    argparser.add_argument('-f', '--fps', default=10, type=int, help='framerate')
    argparser.add_argument('-d', '--days', default=1, type=int, help='process last days photos')
    argparser.add_argument('-o', '--output', metavar='FILENAME', default='output.mp4', help='output mp4 file')
    argparser.add_argument('-n', '--num-procs', metavar='NUM', type=int, default=os.cpu_count() - 1,
                           help='number of subprocesses')
    argparser.add_argument('photo_dir', metavar='DIR', help='directory with photos')
    args = argparser.parse_args()


    def callback(perc):
        print(f'progress {perc:.0f}%')


    try:
        timelapse(args.photo_dir, args.output, days=args.days,
                  fps=args.fps, resize_ratio=args.resize_ratio, codec_opt=args.codec_opt,
                  procs=args.num_procs, progress_callback=callback, progress_period=args.progress_period)
        exit(0)
    except Exception as e:
        print(e)
        exit(1)
