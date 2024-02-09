import os
import time
import hashlib
import requests
import json
import sqlalchemy
import pandas
import xmltodict
import configparser
import re

# Database Configuration
db_info = {
    "host": "127.0.0.1",
    "port": "3306",
    "user": "maccms_spider",
    "pass": "maccms_spider",
    "name": "maccms10",
    "prefix": "mac_",
    "charset": "utf8mb4"
}
site_url = "https://www.maccms10.local"
site_receive_address = {  # store data API
    "_1": "/api.php/receive/vod",
    "_2": "/api.php/receive/art",
    "_8": "/api.php/receive/actor",
    "_9": "/api.php/receive/role",
    "_11": "/api.php/receive/website",
    "multi": {
        "_1": "/api.php/receive/multi_vods"
    }
}
# you should add this function to ./application/api/controller/Receive.php after __construct() function
# or convert array from ./application/extra/bind.php to variable bind_type,
#########################################
# public function type_bind() {
#     echo json_encode(config('bind'));
# }
#########################################
site_bind_type_address = "/api.php/receive/type_bind"
site_receive_pass = "thisissitereceivepass"
# collect_type = 1  # collect resources type, 1: Video, 2: Article, 8: Actor, 9: Role, 11: Website
collect_time = 1  # what time period is the data collected, unit: hours, 0 is unlimited
sleep_time = 0.1  # time to sleep for everytime catch data. unit: seconds
uag = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
storage_file = "maccms10_spider.json"
is_update_type_bind = True
timer_ready_2_write = 10  # how many pages write record to storage file
which_target_2_start = 1  # started with which target by ID, 1 is default
which_target_2_start_page = 1  # started with which page num, 1 is default
save_data_which_target_2_start = 1  # save data started with which target by ID, 1 is default
save_data_which_target_2_start_page = 1  # save data started with which page num, 1 is default
use_multi_api = 1  # use multi API, 1: True, 0: False
everytime_pages_data = pow(2, 2)  # send data everytime
time_force_update = 8  # force update time, unit: hours
save_media_data = 0  # save media data to file, default: 0 is No
# the file in ./application/extra/bind.php
# bind_type = {
#     "7a4856e7b6a1e1a2580a9b69cdc7233c_5": 6,
#     "2b60e6889c35d2e4325dfedf1ab9028e_1": 1,
#     "2b60e6889c35d2e4325dfedf1ab9028e_2": 2
# }
config = []


# calc md5 value
def calc_md5(text=""):
    m = hashlib.md5()
    m.update(text.encode())
    return m.hexdigest()


# clean dict and list
def cleanDL(data):
    if isinstance(data, dict):
        return {k: cleanDL(v) for k, v in data.items() if v or v == 0}
    elif isinstance(data, list):
        return [cleanDL(v) for v in data if v or v == 0]
    else:
        return data


# get color code
def getColorCode(text_color):
    res_color = ""
    if text_color == "red":
        res_color = "\033[31m"
    elif text_color == "green":  # green
        res_color = "\033[32m"
    elif text_color == "yellow":  # yellow
        res_color = "\033[33m"
    elif text_color == "blue":  # blue
        res_color = "\033[34m"
    elif text_color == "purple":  # purple
        res_color = "\033[35m"
    elif text_color == "cyan":  # cyan
        res_color = "\033[36m"
    else:  # white
        res_color = "\033[37m"
    return res_color


# print result
def colorPrint(data):
    for key_res, value_res in enumerate(data):
        print(getColorCode(value_res["color"]) + "%(id)s - %(name)s: %(msg)s" % value_res + "\033[0m")
        if not value_res["download"] is None and len(value_res["download"]) > 0:
            print(getColorCode(value_res["download"]["color"]) + "download a file save to %(path)s, Message is %(msg)s" % value_res["download"] + "\033[0m")


# define msg format
def msg(code=200, message=None, data=None):
    return {
        "code": code,
        "message": message,
        "data": data
    }


# read storage file
def readStorageFile():
    isExist = os.path.exists(config["default"]["storage_file"])
    if isExist:
        file = open(config["default"]["storage_file"], "r")
        file_list = json.load(file)
        return msg(200, "读取完成", file_list)
    else:
        return msg(404, "存储文件不存在", None)


# write storage file
def writeStorageFile(data=None, overwrite=False):
    if data is None:
        data = {}
    if not overwrite:
        res_storage_file = readStorageFile()
        if res_storage_file["code"] == 200:
            storage_file_data = res_storage_file["data"]
        else:
            return res_storage_file
        if "data" in data.keys() and len(data["data"]) > 0 \
                and "data" in storage_file_data.keys() and len(storage_file_data["data"]) > 0:
            for key in data["data"].keys():
                if key in storage_file_data["data"].keys():
                    storage_file_data["data"][key].update(data["data"][key])
                else:
                    storage_file_data["data"][key] = data["data"][key]
        else:
            storage_file_data.update(data)
    else:
        storage_file_data = data

    storage_file_data["update_time"] = int(time.time())

    file = open(config["default"]["storage_file"], "w")
    json.dump(storage_file_data, file, indent=4)
    return msg(200, "写入完成", None)


# load .env
def load_env():
    # Load environment variables from .env file
    config = configparser.ConfigParser()
    config.read(".env")
    # Get all items from the .env file
    items_default = dict(config.items("default"))
    items_default['site_receive_address'] = json.loads(items_default["site_receive_address"])
    items_default['collect_time'] = int(items_default['collect_time'])
    items_default['sleep_time'] = float(items_default['sleep_time'])
    items_default['is_update_type_bind'] = (
            items_default['is_update_type_bind'] == "1" or items_default['is_update_type_bind'] == 1)
    items_default['timer_ready_2_write'] = int(items_default['timer_ready_2_write'])
    items_default['which_target_2_start'] = int(items_default['which_target_2_start'])
    items_default['which_target_2_start_page'] = int(items_default['which_target_2_start_page'])
    items_default['save_data_which_target_2_start'] = int(items_default['save_data_which_target_2_start'])
    items_default['save_data_which_target_2_start_page'] = int(items_default['save_data_which_target_2_start_page'])
    items_default['use_multi_api'] = (items_default['use_multi_api'] == "1" or items_default['use_multi_api'] == 1
                                      or items_default['use_multi_api'] == "True"
                                      or items_default['use_multi_api'] is True)
    items_default['everytime_pages_data'] = int(items_default['everytime_pages_data'])
    items_default['time_force_update'] = int(items_default['time_force_update'])
    items_default['save_media_data'] = (items_default['save_media_data'] == 1 or items_default['save_media_data'] == "1"
                                        or items_default['save_media_data'] is True
                                        or items_default['save_media_data'] == "True")
    # items_default["bind_type"] = json.loads(items_default["bind_type"])
    # Return items as a dictionary
    return {"default": items_default, "db": dict(config.items("db"))}


# load config
def load_config():
    isExist = os.path.exists(".env")
    if isExist:
        data_config = load_env()
    else:
        data_config = {
            "default": {
                "site_url": site_url,
                "site_receive_address": site_receive_address,
                "site_bind_type_address": site_bind_type_address,
                "site_receive_pass": site_receive_pass,
                "collect_time": int(collect_time),
                "sleep_time": float(sleep_time),
                "uag": uag,
                "storage_file": storage_file,
                "is_update_type_bind": bool(is_update_type_bind),
                "timer_ready_2_write": int(timer_ready_2_write),
                "which_target_2_start": int(which_target_2_start),
                "which_target_2_start_page": int(which_target_2_start_page),
                "save_data_which_target_2_start": int(save_data_which_target_2_start),
                "save_data_which_target_2_start_page": int(save_data_which_target_2_start_page),
                "use_multi_api": (
                        use_multi_api == "1" or use_multi_api == 1
                        or use_multi_api is True or use_multi_api == "True"),
                "everytime_pages_data": int(everytime_pages_data),
                "time_force_update": int(time_force_update),
                "save_media_data": (
                        save_media_data == "1" or save_media_data == 1
                        or save_media_data is True or save_media_data == "True"),
                # "bind_type": bind_type
            },
            "db": {
                "host": db_info["host"],
                "port": db_info["port"],
                "user": db_info["user"],
                "pass": db_info["pass"],
                "name": db_info["name"],
                "prefix": db_info["prefix"],
                "charset": db_info["charset"]
            }
        }
    return data_config


# get Collect Resources address
def getCollectAddressInfo():
    print("正在获取资源站信息")
    db_engine = sqlalchemy.create_engine(
        "mysql+pymysql://%(db_user)s:%(db_pass)s@%(db_host)s:%(db_port)s/%(db_name)s?charset=%(db_charset)s" % config[
            "db"])
    db_connect = db_engine.connect()
    data_sql = pandas.read_sql(sqlalchemy.text("select * from " + config["db"]["db_prefix"] + "collect"), db_connect)
    list_data_sql = data_sql.values.tolist()
    data_collect_address = []
    for key in range(0, len(list_data_sql)):
        data_collect_address.append({
            "id": list_data_sql[key][0],
            "name": list_data_sql[key][1],
            "url": list_data_sql[key][2],
            "type": list_data_sql[key][3],  # 1: xml, 2: json
            "mid": list_data_sql[key][4]  # 1: Video, 2: Article, 8: Actor, 9: Role, 11: Website
        })
    return data_collect_address


# get target info & meta data
def getTargetInfo(url=None, rtype=1):
    if url is None:
        return msg(204, "Your target address is empty", None)
    gti_params = {
        "ac": "list"
    }
    if type(config["default"]["collect_time"]) is int and config["default"]["collect_time"] > 0:
        gti_params.update({"h": config["default"]["collect_time"]})
    result_data = {"code": 0, "msg": "This is default msg", "data": None}
    response = requests.get(url, params=gti_params, headers={"User-Agent": config["default"]["uag"]})
    if response.status_code == 200:
        if rtype == 1:
            res_response_data = json.loads(json.dumps(xmltodict.parse(response.text), indent=1))
            response_data_list = []
            res_response_data_rss_list_video = res_response_data["rss"]["list"]["video"]
            for key in range(0, len(res_response_data_rss_list_video)):
                response_data_list.append({
                    "vod_id": res_response_data_rss_list_video[key]["id"],
                    "vod_name": res_response_data_rss_list_video[key]["name"],
                    "type_id": res_response_data_rss_list_video[key]["name"],
                    "type_name": res_response_data_rss_list_video[key]["name"],
                    "vod_en": None,
                    "vod_time": res_response_data_rss_list_video[key]["last"],
                    "vod_remarks": res_response_data_rss_list_video[key]["note"],
                    "vod_play_from": res_response_data_rss_list_video[key]["dt"],
                    "vod_play_url": None
                })
            response_data_class = []
            res_response_data_rss_class_ty = res_response_data["rss"]["class"]["ty"]
            for key in range(0, len(res_response_data_rss_class_ty)):
                response_data_class.append({
                    "type_id": res_response_data_rss_class_ty[key]["@id"],
                    "type_pid": None,
                    "type_name": res_response_data_rss_class_ty[key]["#text"]
                })
            response_data = {
                "code": 1,
                "msg": "数据列表",
                "page": res_response_data["rss"]["list"]["@page"],
                "pagecount": res_response_data["rss"]["list"]["@pagecount"],
                "limit": res_response_data["rss"]["list"]["@pagesize"],
                "total": res_response_data["rss"]["list"]["@recordcount"],
                "list": response_data_list,
                "class": response_data_class
            }
        elif rtype == 2:
            response_data = json.loads(response.text)
        else:
            return msg(500, "采集格式错误", None)
        gti_data = {
            "code": response_data["code"],
            "msg": response_data["msg"],
            "page": response_data["page"],
            "page_count": response_data["pagecount"],
            "limit": response_data["limit"],
            "total": response_data["total"],
            "class": response_data["class"]
        }
        result_data["code"] = 200
        result_data["msg"] = "数据获取成功"
        result_data["data"] = gti_data
    else:
        result_data["code"] = response.status_code
        result_data["msg"] = "数据获取失败"
        result_data["data"] = {"msg": response.text}
    return msg(result_data["code"], result_data["msg"], result_data["data"])


def getTypeBind():
    utb_params = {
        "pass": config["default"]["site_receive_pass"]
    }
    result_data = {"code": 0, "msg": "This is default msg", "data": None}
    response = requests.get(config["default"]["site_url"] + config["default"]["site_bind_type_address"],
                            params=utb_params, headers={"User-Agent": config["default"]["uag"]})
    if response.status_code == 200:
        result_data["code"] = 200
        result_data["msg"] = "类型绑定数据获取成功"
        result_data["data"] = json.loads(response.text)
    else:
        result_data["code"] = response.status_code
        result_data["msg"] = "类型绑定数据获取失败, 错误原因: " + response.text
        result_data["data"] = None
    return msg(result_data["code"], result_data["msg"], result_data["data"])


def processMediaData():
    print("正在尝试获取资源信息")
    meta_data = readStorageFile()
    if meta_data["code"] == 200 \
            and len(meta_data["data"]) <= 0 \
            and "target_info" in meta_data["data"].keys() \
            and len(meta_data["data"]["target_info"]) <= 0:
        return msg(500, "请先获取元数据", None)
    if ("update_time" not in meta_data["data"].keys()
            or (meta_data["data"]["update_time"] + 3600 * config["default"]["time_force_update"]) <= int(time.time())):
        res_gmi = getMetaInfo()
        print("元数据信息过期, 重新获取. 代码为: " + str(res_gmi["code"]) + " 消息为: " + res_gmi["message"])
        meta_data = readStorageFile()
    target_info = meta_data["data"]["target_info"]
    result_data = {}  # id_1: []

    # start with which target source
    target_info_start_with_id = 1
    if config["default"]["which_target_2_start"] > 1:
        for key, value in enumerate(target_info):
            if config["default"]["which_target_2_start"] == value["id"]:
                target_info_start_with_id = value["id"]
                break

    # start with which page
    target_info_start_with_id_page = 1
    is_ready_2_start = False
    if config["default"]["which_target_2_start_page"] > 1:
        target_info_start_with_id_page = config["default"]["which_target_2_start_page"]

    timer_ready_2_write_start = 0
    for key_ti, value_ti in enumerate(target_info):
        if value_ti["id"] >= target_info_start_with_id:
            is_ready_2_start = True
        if is_ready_2_start:
            media_data = {}  # page_1: []
            print("正在获取 " + value_ti["name"] + " 的数据")
            gmd_params = {
                "ac": "detail",
                "pg": target_info_start_with_id_page,
                "h": config["default"]["collect_time"]
            }
            for key_page in range(target_info_start_with_id_page, int(value_ti["data"]["page_count"]) + 1):
                time.sleep(config["default"]["sleep_time"])  # to sleep
                print("正在获取 " + value_ti["name"] + " 第 " + str(gmd_params["pg"]) + "/" + str(
                    value_ti["data"]["page_count"]) + " 页")
                response = requests.get(
                    value_ti["url"],
                    params=gmd_params,
                    headers={"User-Agent": config["default"]["uag"]}
                )
                if response.status_code == 200:
                    # template_data = {
                    #     "vod_id": None,  # 影片 id
                    #     "type_id": None,  # 类别 id
                    #     "type_id_1": None,  # 父级类别 id
                    #     # "group_id": None,  # 组 id
                    #     "vod_name": None,  # 影片名称
                    #     "vod_sub": None,  # 子标题
                    #     "vod_en": None,  # 英文名
                    #     "vod_status": None,  # 是否审核 1/0
                    #     "vod_letter": None,  # 首字母
                    #     "vod_color": None,  # 颜色, RGB 不包含#
                    #     "vod_tag": None,  # 标签
                    #     "vod_class": None,  # 扩展分类
                    #     "vod_pic": None,  # 图片
                    #     "vod_pic_thumb": None,  # 图片缩略图
                    #     "vod_pic_slide": None,  # 海报图
                    #     "vod_pic_screenshot": None,  # 截图
                    #     "vod_actor": None,  # 演员
                    #     "vod_director": None,  # 导演
                    #     "vod_writer": None,  # 编剧
                    #     "vod_behind": None,  # 幕后
                    #     "vod_blurb": None,  # 简介
                    #     "vod_remarks": None,  # 备注
                    #     "vod_pubdate": None,  # 发布日期, 2018-01-20
                    #     "vod_total": None,  # 总集数, 100
                    #     "vod_serial": None,  # 连载数, 20
                    #     "vod_tv": None,  # 电视频道
                    #     "vod_weekday": None,  # 节目周期
                    #     "vod_area": None,  # 地区, 大陆
                    #     "vod_lang": None,  # 语言, 国语
                    #     "vod_year": None,  # 年份, 2018
                    #     "vod_version": None,  # 资源版本, 高清版
                    #     "vod_state": None,  # 资源类别, 正片, 预告片, 花絮
                    #     "vod_author": None,  # 作者, 作者
                    #     "vod_jumpurl": None,  # 跳转URL
                    #     # "vod_tpl": None,  # 内容页模板
                    #     # "vod_tpl_play": None,  # 播放页模板
                    #     # "vod_tpl_down": None,  # 下载页模板
                    #     "vod_isend": None,  # 已/未完结
                    #     "vod_lock": None,  # 锁定/解锁
                    #     # "vod_level": None,  # 推荐 1-9, 9:幻灯片
                    #     # "vod_copyright": None,  # 开启/关闭版权处理
                    #     # "vod_points": None,  # 整数据积分
                    #     # "vod_points_play": None,  # 播放积分
                    #     # "vod_points_down": None,  # 下载积分
                    #     # "vod_hits": None,  # 人气
                    #     # "vod_hits_day": None,  # 日人气
                    #     # "vod_hits_week": None,  # 周人气
                    #     # "vod_hits_month": None,  # 月人气
                    #     "vod_duration": None,  # 视频时长
                    #     # "vod_up": None,  # 顶
                    #     # "vod_down": None,  # 踩
                    #     # "vod_score": None,  # 平均分
                    #     # "vod_score_all": None,  # 总评分
                    #     # "vod_score_num": None,  # 总评次
                    #     # "vod_time": None,  # 更新时间(时间戳), 系统自动更新
                    #     # "vod_time_add": None,  # 视频添加时间(时间戳), 系统自动更新
                    #     # "vod_time_hits": None,  #
                    #     # "vod_time_make": None,  #
                    #     # "vod_trysee": None,  #
                    #     "vod_douban_id": None,  # 豆瓣ID
                    #     "vod_douban_score": None,  # 豆瓣评分
                    #     # "vod_reurl": None,  #
                    #     # "vod_rel_vod": None,  # 关联视频ID, 多个以英文半角逗号分割
                    #     # "vod_rel_art": None,  # 关联文章ID, 多个以英文半角逗号分割
                    #     # "vod_pwd": None,  # 内容页密码
                    #     # "vod_pwd_url": None,  # 密码链接内容页
                    #     # "vod_pwd_play": None,  # 播放页密码
                    #     # "vod_pwd_play_url": None,  # 密码链接播放页
                    #     # "vod_pwd_down": None,  # 下载页密码
                    #     # "vod_pwd_down_url": None,  # 密码链接下载页
                    #     "vod_content": None,  # 详情, 介绍
                    #     "vod_play_from": None,  # 视频资源播放标签, xlm3u8
                    #     # "vod_play_server": None,  # 播放服务器, 全球服务器(server1)
                    #     # "vod_play_note": None,  # 播放服务器备注
                    #     "vod_play_url": None,  # 播放资源 url
                    #     # "vod_down_from": None,  # 下载资源类型, http/xunlei
                    #     # "vod_down_server": None,  # 下载服务器, 全球服务器(server1)
                    #     # "vod_down_note": None,  # 下载服务器备注
                    #     # "vod_down_url": None,  # 下载资源 url
                    #     # "vod_plot": None,  # 是否开启分集剧情
                    #     # "vod_plot_name": None,  # 分集剧情标题
                    #     # "vod_plot_detail": None,  # 分集剧情内容
                    #     # "type_name": None # 不提交类别名称
                    # }
                    if value_ti["type"] == 1:
                        res_response_data = json.loads(json.dumps(xmltodict.parse(response.text), indent=1))
                        response_data_list = []
                        res_rdrlv = res_response_data["rss"]["list"]["video"]  # result response data rss list video
                        for key_data in range(0, len(res_rdrlv)):
                            template_data = {
                                # "vod_id": res_rdrlv[key_data]["id"],
                                "type_id": res_rdrlv[key_data]["tid"],
                                "vod_name": res_rdrlv[key_data]["name"],
                                "vod_pic": res_rdrlv[key_data]["pic"],
                                "vod_lang": res_rdrlv[key_data]["lang"],
                                "vod_area": res_rdrlv[key_data]["area"],
                                "vod_year": res_rdrlv[key_data]["year"],
                                "vod_state": res_rdrlv[key_data]["state"],
                                "vod_remarks": res_rdrlv[key_data]["note"],
                                "vod_actor": res_rdrlv[key_data]["actor"],
                                "vod_director": res_rdrlv[key_data]["director"],
                                "vod_play_from": "",
                                "vod_play_url": "",
                                "vod_content": res_rdrlv[key_data]["des"]
                            }

                            if type(res_rdrlv[key_data]["dl"]["dd"]) is dict:
                                template_data["vod_play_from"] = res_rdrlv[key_data]["dl"]["dd"]["@flag"]
                                template_data["vod_play_url"] = res_rdrlv[key_data]["dl"]["dd"]["#text"]
                            elif type(res_rdrlv[key_data]["dl"]["dd"]) is list:
                                list_data_dd = []
                                for key_dd, value_dd in enumerate(res_rdrlv[key_data]["dl"]["dd"]):
                                    dl_insert = True
                                    for key_dd_list, value_dd_list in enumerate(list_data_dd):
                                        if value_dd_list["#text"] == value_dd["#text"]:
                                            dl_insert = False
                                            break

                                        if value_dd_list["@flag"] == value_dd["@flag"]:
                                            dl_insert = False
                                            value_dd_list["#text"] += ("#"+value_dd["#text"])
                                            break

                                    if dl_insert:
                                        list_data_dd.append({
                                            "@flag": value_dd["@flag"],
                                            "#text": value_dd["#text"]
                                        })

                                for key_dd_list, value_dd_list in enumerate(list_data_dd):
                                    template_data["vod_play_from"] += ("$$$"+value_dd_list["@flag"])
                                    template_data["vod_play_url"] += ("$$$"+value_dd_list["#text"])

                                if template_data["vod_play_from"].startswith("$$$", 0):
                                    template_data["vod_play_from"] = template_data["vod_play_from"][3:]

                                if template_data["vod_play_url"].startswith("$$$", 0):
                                    template_data["vod_play_url"] = template_data["vod_play_url"][3:]

                            response_data_list.append(template_data)

                        media_data["page_" + str(gmd_params["pg"])] = response_data_list
                        timer_ready_2_write_start += 1
                    elif value_ti["type"] == 2:
                        response_data = json.loads(response.text)
                        list_rd = response_data["list"]  # list response data
                        response_data_list = []
                        for key_l3 in range(0, len(list_rd)):
                            template_data = {
                                # 影片 id
                                # "vod_id": list_rd[key_l3]["vod_id"],
                                # 类别 id
                                "type_id":
                                    list_rd[key_l3]["type_id"] if ("type_id" in list_rd[key_l3].keys()) else None,
                                # 父级类别 id
                                # "type_id_1": list_rd[key_l3]["type_id_1"],
                                # 影片名称
                                "vod_name":
                                    list_rd[key_l3]["vod_name"] if ("vod_name" in list_rd[key_l3].keys()) else None,
                                # 子标题
                                "vod_sub":
                                    list_rd[key_l3]["vod_sub"] if ("vod_sub" in list_rd[key_l3].keys()) else None,
                                # 英文名
                                "vod_en":
                                    list_rd[key_l3]["vod_en"] if ("vod_en" in list_rd[key_l3].keys()) else (
                                        list_rd[key_l3]["vod_enname"] if ("vod_enname" in list_rd[key_l3].keys()) else None),
                                # 是否审核 1/0
                                "vod_status":
                                    list_rd[key_l3]["vod_status"] if ("vod_status" in list_rd[key_l3].keys()) else None,
                                # 首字母
                                "vod_letter":
                                    list_rd[key_l3]["vod_letter"] if ("vod_letter" in list_rd[key_l3].keys()) else None,
                                # 颜色, RGB 不包含#
                                "vod_color":
                                    list_rd[key_l3]["vod_color"] if ("vod_color" in list_rd[key_l3].keys()) else None,
                                # 标签
                                "vod_tag":
                                    list_rd[key_l3]["vod_tag"] if ("vod_tag" in list_rd[key_l3].keys()) else None,
                                # 扩展分类
                                "vod_class":
                                    list_rd[key_l3]["vod_class"] if ("vod_class" in list_rd[key_l3].keys()) else None,
                                # 图片
                                "vod_pic":
                                    list_rd[key_l3]["vod_pic"] if ("vod_pic" in list_rd[key_l3].keys()) else None,
                                # 图片缩略图
                                "vod_pic_thumb":
                                    list_rd[key_l3]["vod_pic_thumb"] if ("vod_pic_thumb" in list_rd[key_l3].keys()) else None,
                                # 海报图
                                "vod_pic_slide":
                                    list_rd[key_l3]["vod_pic_slide"] if ("vod_pic_slide" in list_rd[key_l3].keys()) else None,
                                # 截图
                                "vod_pic_screenshot":
                                    list_rd[key_l3]["vod_pic_screenshot"] if ("vod_pic_screenshot" in list_rd[key_l3].keys()) else None,
                                # 演员
                                "vod_actor":
                                    list_rd[key_l3]["vod_actor"] if ("vod_actor" in list_rd[key_l3].keys()) else None,
                                # 导演
                                "vod_director":
                                    list_rd[key_l3]["vod_director"] if ("vod_director" in list_rd[key_l3].keys()) else None,
                                # 编剧
                                "vod_writer":
                                    list_rd[key_l3]["vod_writer"] if ("vod_writer" in list_rd[key_l3].keys()) else None,
                                # 幕后
                                "vod_behind":
                                    list_rd[key_l3]["vod_behind"] if ("vod_behind" in list_rd[key_l3].keys()) else None,
                                # 简介
                                "vod_blurb":
                                    list_rd[key_l3]["vod_blurb"] if ("vod_blurb" in list_rd[key_l3].keys()) else None,
                                # 备注
                                "vod_remarks":
                                    list_rd[key_l3]["vod_remarks"] if ("vod_remarks" in list_rd[key_l3].keys()) else None,
                                # 发布日期, 2018-01-20
                                "vod_pubdate":
                                    list_rd[key_l3]["vod_pubdate"] if ("vod_pubdate" in list_rd[key_l3].keys()) else None,
                                # 总集数, 100
                                "vod_total":
                                    list_rd[key_l3]["vod_total"] if ("vod_total" in list_rd[key_l3].keys()) else None,
                                # 连载数, 20
                                "vod_serial":
                                    list_rd[key_l3]["vod_serial"] if ("vod_serial" in list_rd[key_l3].keys()) else None,
                                # 电视频道
                                "vod_tv":
                                    list_rd[key_l3]["vod_tv"] if ("vod_tv" in list_rd[key_l3].keys()) else None,
                                # 节目周期
                                "vod_weekday":
                                    list_rd[key_l3]["vod_weekday"] if ("vod_weekday" in list_rd[key_l3].keys()) else None,
                                # 地区, 大陆
                                "vod_area":
                                    list_rd[key_l3]["vod_area"] if ("vod_area" in list_rd[key_l3].keys()) else None,
                                # 语言, 国语
                                "vod_lang":
                                    list_rd[key_l3]["vod_lang"] if ("vod_lang" in list_rd[key_l3].keys()) else None,
                                # 年份, 2018
                                "vod_year":
                                    list_rd[key_l3]["vod_year"] if ("vod_year" in list_rd[key_l3].keys()) else None,
                                # 资源版本, 高清版
                                "vod_version":
                                    list_rd[key_l3]["vod_version"] if ("vod_version" in list_rd[key_l3].keys()) else None,
                                # 资源类别, 正片, 预告片, 花絮
                                "vod_state":
                                    list_rd[key_l3]["vod_state"] if ("vod_state" in list_rd[key_l3].keys()) else None,
                                # 作者, 作者
                                "vod_author":
                                    list_rd[key_l3]["vod_author"] if ("vod_author" in list_rd[key_l3].keys()) else None,
                                # 跳转URL
                                "vod_jumpurl":
                                    list_rd[key_l3]["vod_jumpurl"] if ("vod_jumpurl" in list_rd[key_l3].keys()) else None,
                                # 已/未完结
                                "vod_isend":
                                    list_rd[key_l3]["vod_isend"] if ("vod_isend" in list_rd[key_l3].keys()) else None,
                                # 锁定/解锁
                                "vod_lock":
                                    list_rd[key_l3]["vod_lock"] if ("vod_lock" in list_rd[key_l3].keys()) else None,
                                # 视频时长
                                "vod_duration":
                                    list_rd[key_l3]["vod_duration"] if ("vod_duration" in list_rd[key_l3].keys()) else None,
                                # 豆瓣ID
                                "vod_douban_id":
                                    list_rd[key_l3]["vod_douban_id"] if ("vod_douban_id" in list_rd[key_l3].keys()) else None,
                                # 豆瓣评分
                                "vod_douban_score":
                                    list_rd[key_l3]["vod_douban_score"] if ("vod_douban_score" in list_rd[key_l3].keys()) else None,
                                # 详情, 介绍
                                "vod_content":
                                    list_rd[key_l3]["vod_content"] if ("vod_content" in list_rd[key_l3].keys()) else None,
                                # 视频资源播放标签, xlm3u8
                                "vod_play_from":
                                    list_rd[key_l3]["vod_play_from"] if ("vod_play_from" in list_rd[key_l3].keys()) else None,
                                # 播放资源 url
                                "vod_play_url":
                                    list_rd[key_l3]["vod_play_url"] if ("vod_play_url" in list_rd[key_l3].keys()) else None
                            }
                            response_data_list.append(template_data)
                        media_data["page_" + str(gmd_params["pg"])] = response_data_list
                        timer_ready_2_write_start += 1
                    else:
                        return msg(500, "采集格式错误", None)
                    if timer_ready_2_write_start >= config["default"]["timer_ready_2_write"] \
                            and config["default"]["save_media_data"]:
                        res_timer_r2w = writeStorageFile({"data": {"id_" + str(value_ti["id"]): media_data}}, False)
                        if res_timer_r2w["code"] == 200:
                            media_data = {}
                        print(str(value_ti["id"]) + ". " + str(value_ti["name"]) + value_ti["name"] + " 第 "
                              + str(gmd_params["pg"]) + "/" + str(value_ti["data"]["page_count"])
                              + " 页: " + res_timer_r2w["message"])
                        timer_ready_2_write_start = 0
                else:
                    print("获取媒体数据失败, 失败原因: " + response.text)
                gmd_params["pg"] += 1
                if not config["default"]["save_media_data"] \
                        and len(media_data) >= config["default"]["everytime_pages_data"]:
                    processData(media_data, meta_data["data"]["type_bind"], value_ti)
                    media_data = {}

            if not config["default"]["save_media_data"] and len(media_data) > 0:
                processData(media_data, meta_data["data"]["type_bind"], value_ti)
                media_data = {}
            gmd_params["pg"] = 1
            result_data["id_" + str(value_ti["id"])] = media_data
            target_info_start_with_id_page = 1

    if not config["default"]["save_media_data"]:
        result = msg(200, "数据处理完成", None)
    else:
        result = writeStorageFile({"data": result_data}, False)

    return result


# get Resources Meta Info
def getMetaInfo():
    read_mi = readStorageFile()
    if (read_mi["code"] == 200 and len(read_mi["data"]) >= 0
            and "update_time" in read_mi["data"]
            and (read_mi["data"]["update_time"] + 3600 * config["default"]["time_force_update"]) > int(time.time())):
        return msg(200, "资源站元数据读取成功", None)
    resources_info = getCollectAddressInfo()
    for key in range(0, len(resources_info)):
        print("正在获取资源站 " + resources_info[key]["name"] + " 元数据")
        res_target_info = getTargetInfo(resources_info[key]["url"], resources_info[key]["type"])
        if res_target_info["code"] == 200:
            resources_info[key]["data"] = res_target_info["data"]
        else:
            print(json.dumps(res_target_info, encoding="UTF-8"))
    write_data = {"target_info": resources_info}
    if config["default"]["is_update_type_bind"]:
        data_type_bind = getTypeBind()
        if not data_type_bind["code"] == 200:
            print(data_type_bind["message"])
            exit()
        else:
            write_data["type_bind"] = data_type_bind["data"]
    print("正在尝试写入资源站元数据")
    res_sources_data = writeStorageFile(write_data, False)
    return res_sources_data


# multi data process
def multiProcessData(data):
    for key_multi, value_multi in data.items():
        res_sd = sendData(
            {"pass": config["default"]["site_receive_pass"], "arr_data": json.dumps(value_multi)},
            config["default"]["site_url"] + config["default"]["site_receive_address"]["multi"][key_multi]
        )
        if res_sd["code"] == 200 and len(res_sd["data"]) > 0:
            data[key_multi] = []
            colorPrint(res_sd["data"])
        else:
            print("代码为: " + str(res_sd["code"]) + ", 消息为: " + res_sd["message"])


# prepare process data
def pprocessData():
    data = readStorageFile()["data"]
    if ("target_info" not in data.keys()) \
            and ("type_bind" not in data.keys()) \
            and ("data" not in data.keys()):
        return msg(500, "target_info 或 type_bind 或 data 数据不存在", None)
    if len(data["target_info"]) <= 0:
        return msg(500, "target_info 数据不能为空", None)
    if len(data["type_bind"]) <= 0:
        return msg(500, "type_bind 数据不能为空", None)
    if len(data["data"]) <= 0:
        return msg(500, "data 数据不能为空", None)

    target_info = data["target_info"]
    type_bind = data["type_bind"]
    res_data = data["data"]
    del data

    # start with which target source
    target_info_start_with_id = 0
    if config["default"]["save_data_which_target_2_start"] >= 1:
        for key, value in res_data.items():
            if ("id_" + str(config["default"]["save_data_which_target_2_start"])) == key:
                target_info_start_with_id = config["default"]["save_data_which_target_2_start"]
                break

    # start with which page
    target_info_start_with_id_page = 1
    if config["default"]["save_data_which_target_2_start_page"] > 1:
        target_info_start_with_id_page = config["default"]["save_data_which_target_2_start_page"]

    key_id_start = False
    key_page_start = False
    timer_key_data = {}
    for key_id, value_id in res_data.items():
        if key_id_start or key_id == "id_" + str(target_info_start_with_id):
            key_id_start = True

        # matched target info
        temp_ti = {}
        for key_ti, value_ti in enumerate(target_info):
            if "id_" + str(value_ti["id"]) == key_id:
                temp_ti = value_ti
                break
        if key_id_start:
            print("正在处理 " + temp_ti["name"] + ", 预计 " + str(temp_ti["data"]["total"]) + " 条数据")

            if len(value_id) <= 0:
                print("未找到有关 " + temp_ti["name"] + " 的数据")
                continue

            for key_page, value_page in value_id.items():  # per page data
                if key_page_start or key_page == "page_" + str(target_info_start_with_id_page):
                    key_page_start = True

                if key_page_start:
                    timer_key_data[key_page] = value_page
                    if len(timer_key_data) >= config["default"]["everytime_pages_data"]:
                        processData(timer_key_data, type_bind, temp_ti)

            if len(timer_key_data) > 0:
                processData(timer_key_data, type_bind, temp_ti)

        else:
            print(str(temp_ti["id"]) + ": " + temp_ti["name"] + " 第 " + key_id[3:] + " 页已被跳过")
    return msg(200, "处理完成", None)


# process data
def processData(value_id, type_bind, temp_ti):
    # 用以保存当前不满足批量发送数据数量时的数据
    timer_key_data = {}
    for key_page, value_page in value_id.items():  # per page data

        for key_data, value_data in enumerate(value_page):  # per data
            print("正在处理 " + temp_ti["name"] + " 第 "
                  + str(key_page[5:])+" 页的第 " + str(key_data + 1) + "/" + str(len(value_page)) + " 条数据")
            # 遍历数据中所有空字符串数据, 并删除
            temp_data = cleanDL(value_data)
            type_id_data = calc_md5(temp_ti["url"])
            type_id_data += "_" + str(temp_data["type_id"])
            if type_id_data not in type_bind:
                for key_ti_class, value_ti_class in enumerate(temp_ti["data"]["class"]):
                    if temp_data["type_id"] == value_ti_class["type_id"]:
                        print("名称为 " + temp_data["vod_name"] + " 的媒体数据未绑定类型, 该类型为: " + value_ti_class["type_name"])
                        break
                return False

            temp_data["type_id"] = type_bind[type_id_data]

            if (config["default"]["use_multi_api"] and "multi" in config["default"]["site_receive_address"].keys()
                    and ("_" + str(temp_ti["mid"])) in config["default"]["site_receive_address"]["multi"].keys()):
                # print("本次数据入库方式为: 批量")
                if "_" + str(temp_ti["mid"]) not in timer_key_data.keys():
                    timer_key_data["_" + str(temp_ti["mid"])] = []
                timer_key_data["_" + str(temp_ti["mid"])].append(temp_data)

            else:
                temp_data["pass"] = config["default"]["site_receive_pass"]

                time.sleep(config["default"]["sleep_time"])  # to sleep
                req_url = config["default"]["site_url"] + config["default"]["site_receive_address"][
                    "_" + str(temp_ti["mid"])]
                res_sd = sendData(temp_data, req_url)
                if res_sd["code"] == 200:
                    print(res_sd["message"])
                else:
                    print("代码为: " + str(res_sd["code"]) + ", 消息为: " + res_sd["message"])
    if len(timer_key_data) > 0:
        multiProcessData(timer_key_data)


# send data
def sendData(data=None, req_url=None):
    if req_url is None:
        return msg(500, "请求地址不能为空", None)

    response = requests.post(req_url, data=data, headers={"User-Agent": config["default"]["uag"]})
    if response.status_code == 200:
        if response.text.startswith("[vod_data]"):
            res_text = response.text.replace("&nbsp;", " ")
            res_text_list = cleanDL(res_text.split("<br>"))
            res_data = []
            for key, value in enumerate(res_text_list):
                if value.startswith("[vod_data] ") or value.startswith("数据采集完成。"):
                    res_text_list[key] = ''
                else:
                    matchObj = re.match(r"^(\d*)、(.*) <font color='(.*)'>(.*)。</font>(<a.*>(.*)</a><font color=(.*)>(.*)</font>)*$", value, re.U | re.I)
                    res_data_download = {}
                    if not matchObj.group(5) is None:
                        res_data_download = {
                            "path": matchObj.group(6),
                            "color": matchObj.group(7),
                            "msg": matchObj.group(8)
                        }
                    res_data.append({
                        "id": matchObj.group(1),
                        "name": matchObj.group(2),
                        "color": matchObj.group(3),
                        "msg": matchObj.group(4),
                        "download": res_data_download
                    })
            return msg(200, "数据发送完毕", res_data)
        else:
            response_data = json.loads(response.text)
            return msg(response_data["code"], response_data["msg"], None)
    else:
        return msg(response.status_code, response.text, None)


# follow the process
def process():
    res_meta_info = getMetaInfo()
    print(res_meta_info["message"])

    # 处理媒体数据
    res_pmd = processMediaData()
    print(res_pmd)
    if config["default"]["save_media_data"]:
        res_ppd = pprocessData()
        print(res_ppd)


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    config = load_config()
    process()
