import io
import os
import time
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

import telebot

from timelapse import timelapse

if __name__ == '__main__':
    argparser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    argparser.add_argument('-p', '--progress-period', metavar='SECS', type=int, help='progress print period',
                           default=int(os.getenv('TIMELAPSE_PROG_PERIOD', 3)))
    argparser.add_argument('-r', '--resize-ratio', metavar='RATIO', type=int, help='downscale ratio',
                           default=int(os.getenv('TIMELAPSE_PESIZE_RATIO', 4)))
    argparser.add_argument('-c', '--codec-opt', metavar='OPT', type=int, help='x264 crf',
                           default=int(os.getenv('TIMELAPSE_CODEC_OPT', 23)))
    argparser.add_argument('-f', '--fps', default=int(os.getenv('TIMELAPSE_FPS', 10)), type=int, help='framerate')
    argparser.add_argument('-n', '--num-procs', metavar='NUM', type=int, help='number of subprocesses',
                           default=int(os.getenv('TIMELAPSE_NUM_PROCS', os.cpu_count() - 1)))
    argparser.add_argument('-i', '--id', type=int, action='append',
                           help='whitelisted id, can be multiple specified, by default all ids accepted',
                           default=[int(v) for v in os.getenv('TIMELAPSE_IDS', '').split(' ') if v])
    argparser.add_argument('-t', '--token', metavar='TOKEN', help='telegram bot token',
                           default=os.getenv('TIMELAPSE_TOKEN'))
    argparser.add_argument('photo_dir', metavar='DIR', help='directory with photos')
    args = argparser.parse_args()
    assert args.token is not None, 'you must specify token'

    bot = telebot.TeleBot(args.token)


    @bot.message_handler(commands=['days'], func=lambda message: not args.id or message.chat.id in args.id)
    def start_command(message):
        parts = message.text.split()
        if len(parts) == 2:
            days = int(parts[1])
            print('days', days)

            def callback(perc):
                bot.send_message(message.chat.id, f'progress {perc:.0f}%')

            f = io.BytesIO()
            f.name = f'{time.time():.0f}_{message.chat.id}.mp4'
            try:
                timelapse(args.photo_dir, f, days=days, fps=args.fps, resize_ratio=args.resize_ratio,
                          procs=args.num_procs, progress_callback=callback, progress_period=args.progress_period)
                f.seek(0)
                bot.send_animation(message.chat.id, f)
            except Exception as e:
                bot.send_message(message.chat.id, "Error:" + str(e))
        else:
            bot.send_message(message.chat.id, "Cmd error")


    bot.polling()
