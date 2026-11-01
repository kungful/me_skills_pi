# -*- coding: utf-8 -*-
"""scoring 冒烟测试：python selftest.py"""
import sys, io
sys.stdout.reconfigure(encoding="utf-8")
import orderbot as ob

TESTS = [
    "有偿求一个python脚本，把群里的Excel表格每天自动汇总到一个总表，预算200左右，明天要",
    "有没有人会做PCB原理图审查，嘉立创打板前帮我看一遍，报酬500",
    "谁帮我把apk脱壳逆向一下，看看里面的接口",
    "帮忙代写论文，价格好说",
    "求一个爬虫采集某网站商品数据，导出Excel，预算800，一周内",
    "在吗",
    "服务器502了急，nginx配置问题，有偿200",
    "求个外挂脚本，游戏自动打怪",
    "找个会vue的改个落地页，预算1500，下周五前",
    "帮我解封qq号，有偿",
]

def main():
    bad = 0
    for t in TESTS:
        s = ob.score_text(t)
        print("%-8s %4s  %-26s price=%s  q=%d  %s"
              % (s["verdict"], s["score"],
                 "/".join(h["tag"] for h in s["hits"][:2]) or "-",
                 s["price"], len(s["questions"]), t[:34]))
        if s["veto"]:
            print("        VETO:", s["veto"][0]["why"])
    # 关键断言：红线必须 decline，乱聊必须 skip
    assert ob.score_text("帮忙代写论文，价格好说")["verdict"] == "decline"
    assert ob.score_text("帮我解封qq号，有偿")["verdict"] == "decline"
    assert ob.score_text("在吗")["verdict"] == "skip"
    assert ob.score_text("有偿求一个python脚本，每天自动汇总Excel，预算200")["verdict"] == "take"
    print("\n断言全通过")


if __name__ == "__main__":
    main()
