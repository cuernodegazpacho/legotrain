import statistics as stat

from time import sleep
from colorsys import rgb_to_hsv

from pylgbst.hub import SmartHub


def demo_color_sensor(smart_hub):
    print("Color sensor test: wave your hand in front of it")
    demo_color_sensor.cnt = 0
    limit = 300

    bg_list = []
    gr_list = []
    h_list = []
    s_list = []
    v_list = []

    def callback(*args, **kwargs):
        demo_color_sensor.cnt += 1

        # use HSV as criterion for mapping colors
        r = args[0]
        g = args[1]
        b = args[2]

        h, s, v = rgb_to_hsv(r, g, b)

        if h >= 1. or h <= 0.:
            return

        if max(r, g, b) > 10.0 and v > 20.0:
            h_list.append(h)
            s_list.append(s)
            v_list.append(v)

            bg = b / g
            gr = g / r

            bg_list.append(bg)
            gr_list.append(gr)

            red_detection = "other"
            if (h > 0.93) and (s > 0.60 and s < 0.81):
                red_detection = "RED"
            elif (h > 0.93 and h < 0.98) and (s > 0.53 and s < 0.60):
                red_detection = "YELLOW"
            elif (h > 0.55 and h < 0.62) and (s > 0.50 and s < 0.72):
                red_detection = "LIGHT BLUE"
            elif (h > 0.15 and h < 0.30) and (s > 0.23 and s < 0.55):
                red_detection = "LIGHT GREEN"
            elif (h > 0.40 and h < 0.60) and (s > 0.25 and s < 0.60):
                red_detection = "GREEN"
            elif (h > 0.58 and h < 0.78) and (s > 0.19 and s < 0.40):
                red_detection = "DARK GRAY (track)"


            print(demo_color_sensor.cnt, limit, args, kwargs, h, s, v, bg, gr, red_detection)

    smart_hub.vision_sensor.subscribe(callback, granularity=3, mode=6)

    while demo_color_sensor.cnt < limit:
        sleep(1)

    smart_hub.vision_sensor.unsubscribe(callback)

    print("H stats: ", stat.mean(h_list), stat.stdev(h_list), min(h_list), max(h_list))
    print("S stats: ", stat.mean(s_list), stat.stdev(s_list), min(s_list), max(s_list))
    print("V stats: ", stat.mean(v_list), stat.stdev(v_list), min(v_list), max(v_list))
    print("BG stats: ", stat.mean(bg_list), stat.stdev(bg_list), min(bg_list), max(bg_list))
    print("GR stats: ", stat.mean(gr_list), stat.stdev(gr_list), min(gr_list), max(gr_list))


smart_hub = SmartHub(address='86996732-BF5A-433D-AACE-5611D4C6271D')   # test hub

demo_color_sensor(smart_hub)