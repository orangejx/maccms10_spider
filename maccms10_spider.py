import os
import time
import hashlib
import requests
import json
import sqlalchemy
import pandas
import xmltodict


# Database Configuration
db_info = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "maccms_spider",
    "pass": "maccms_spider",
    "name": "maccms10",
    "prefix": "mac_",
    "charset": "utf8mb4"
}
site_url = "https://www.maccms10.local" 
site_receive_address = {  # store data API
    1: "/api.php/receive/vod",
    2: "/api.php/receive/art",
    8: "/api.php/receive/actor",
    9: "/api.php/receive/role",
    11: "/api.php/receive/website"
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
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
storage_file = "maccms10_spider.json"
is_update_type_bind = True
# the file in ./application/extra/bind.php
bind_type = {
    '7a4856e7b6a1e1a2580a9b69cdc7233c_5': 6,
    '2b60e6889c35d2e4325dfedf1ab9028e_1': 1,
    '2b60e6889c35d2e4325dfedf1ab9028e_2': 2
}


# define msg format
def msg(code=200, message=None, data=None):
    return {
        "code": code,
        "message": message,
        "data": data
    }


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


# get Collect Resources address
def getCollectAddressInfo():
    print("正在获取资源站信息")
    db_engine = sqlalchemy.create_engine(
        "mysql+pymysql://%(user)s:%(pass)s@%(host)s:%(port)s/%(name)s?charset=%(charset)s" % db_info)
    db_connect = db_engine.connect()
    data_sql = pandas.read_sql(sqlalchemy.text("select * from " + db_info["prefix"] + "collect"), db_connect)
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
    if type(collect_time) is int and collect_time > 0:
        gti_params.update({"h": collect_time})
    result_data = {"code": 0, "msg": "This is default msg", "data": None}
    response = requests.get(url, params=gti_params, headers=headers)
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


# read storage file
def readStorageFile():
    isExist = os.path.exists(storage_file)
    if isExist:
        file = open(storage_file, "r")
        file_list = json.load(file)
    else:
        file_list = {}
    return msg(200, "读取完成", file_list)


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
        storage_file_data.update(data)
    else:
        storage_file_data = data

    file = open(storage_file, "w")
    json.dump(storage_file_data, file, indent=4)
    return msg(200, "写入完成", None)


def getTypeBind():
    utb_params = {
        "pass": site_receive_pass
    }
    result_data = {"code": 0, "msg": "This is default msg", "data": None}
    response = requests.get(site_url+site_bind_type_address, params=utb_params, headers=headers)
    if response.status_code == 200:
        result_data["code"] = 200
        result_data["msg"] = "类型绑定数据获取成功"
        result_data["data"] = json.loads(response.text)
    else:
        result_data["code"] = response.status_code
        result_data["msg"] = "类型绑定数据获取失败, 错误原因: "+response.text
        result_data["data"] = None
    return msg(result_data["code"], result_data["msg"], result_data["data"])


def getMediaData():
    print("正在尝试获取资源信息")
    meta_data = readStorageFile()
    if meta_data["code"] == 200 \
            and len(meta_data["data"]) <= 0 \
            and "target_info" in meta_data.keys() \
            and len(meta_data["data"]["target_info"]) <= 0:
        return msg(500, "请先获取元数据", None)
    target_info = meta_data["data"]["target_info"]
    result_data = {}  # id_1: []
    for key in range(0, len(target_info)):
        media_data = {}  # page_1: []
        print("正在获取 "+target_info[key]["name"]+" 的数据")
        gmd_params = {
            "ac": "detail",
            "pg": 0,
            "h": collect_time
        }
        for key_2 in range(0, int(target_info[key]["data"]["page_count"])):
            time.sleep(sleep_time)  # to sleep
            gmd_params["pg"] += 1
            print("正在获取第 "+str(gmd_params["pg"])+"/"+str(target_info[key]["data"]["page_count"])+" 页")
            response = requests.get(target_info[key]["url"], params=gmd_params, headers=headers)
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
                if target_info[key]["type"] == 1:
                    res_response_data = json.loads(json.dumps(xmltodict.parse(response.text), indent=1))
                    response_data_list = []
                    res_rdrlv = res_response_data["rss"]["list"]["video"]  # result response data rss list video
                    for key_l2 in range(0, len(res_rdrlv)):
                        template_data = {
                            # "vod_id": res_rdrlv[key_l2]["id"],
                            "type_id": res_rdrlv[key_l2]["tid"],
                            "vod_name": res_rdrlv[key_l2]["name"],
                            "vod_pic": res_rdrlv[key_l2]["pic"],
                            "vod_lang": res_rdrlv[key_l2]["lang"],
                            "vod_area": res_rdrlv[key_l2]["area"],
                            "vod_year": res_rdrlv[key_l2]["year"],
                            "vod_state": res_rdrlv[key_l2]["state"],
                            "vod_remarks": res_rdrlv[key_l2]["note"],
                            "vod_actor": res_rdrlv[key_l2]["actor"],
                            "vod_director": res_rdrlv[key_l2]["director"],
                            "vod_play_from": res_rdrlv[key_l2]["dl"]["dd"]["@flag"],
                            "vod_play_url": res_rdrlv[key_l2]["dl"]["dd"]["#text"],
                            "vod_content": res_rdrlv[key_l2]["des"]
                        }
                        response_data_list.append(template_data)
                    media_data["page_"+str(gmd_params["pg"])] = response_data_list
                elif target_info[key]["type"] == 2:
                    response_data = json.loads(response.text)
                    list_rd = response_data["list"]  # list response data
                    response_data_list = []
                    for key_l3 in range(0, len(list_rd)):
                        template_data = {
                            # "vod_id": list_rd[key_l3]["vod_id"],  # 影片 id
                            "type_id":
                                list_rd[key_l3]["type_id"] if ("type_id" in list_rd[key_l3].keys()) else None,  # 类别 id
                            # "type_id_1": list_rd[key_l3]["type_id_1"],  # 父级类别 id
                            "vod_name":
                                list_rd[key_l3]["vod_name"] if ("vod_name" in list_rd[key_l3].keys()) else None,  # 影片名称
                            "vod_sub":
                                list_rd[key_l3]["vod_sub"] if ("vod_sub" in list_rd[key_l3].keys()) else None,  # 子标题
                            "vod_en":
                                list_rd[key_l3]["vod_en"] if ("vod_en" in list_rd[key_l3].keys()) else (list_rd[key_l3]["vod_enname"] if ("vod_enname" in list_rd[key_l3].keys()) else None),  # 英文名
                            "vod_status":
                                list_rd[key_l3]["vod_status"] if ("vod_status" in list_rd[key_l3].keys()) else None,  # 是否审核 1/0
                            "vod_letter":
                                list_rd[key_l3]["vod_letter"] if ("vod_letter" in list_rd[key_l3].keys()) else None,  # 首字母
                            "vod_color":
                                list_rd[key_l3]["vod_color"] if ("vod_color" in list_rd[key_l3].keys()) else None,  # 颜色, RGB 不包含#
                            "vod_tag":
                                list_rd[key_l3]["vod_tag"] if ("vod_tag" in list_rd[key_l3].keys()) else None,  # 标签
                            "vod_class":
                                list_rd[key_l3]["vod_class"] if ("vod_class" in list_rd[key_l3].keys()) else None,  # 扩展分类
                            "vod_pic":
                                list_rd[key_l3]["vod_pic"] if ("vod_pic" in list_rd[key_l3].keys()) else None,  # 图片
                            "vod_pic_thumb":
                                list_rd[key_l3]["vod_pic_thumb"] if ("vod_pic_thumb" in list_rd[key_l3].keys()) else None,  # 图片缩略图
                            "vod_pic_slide":
                                list_rd[key_l3]["vod_pic_slide"] if ("vod_pic_slide" in list_rd[key_l3].keys()) else None,  # 海报图
                            "vod_pic_screenshot":
                                list_rd[key_l3]["vod_pic_screenshot"] if ("vod_pic_screenshot" in list_rd[key_l3].keys()) else None,  # 截图
                            "vod_actor":
                                list_rd[key_l3]["vod_actor"] if ("vod_actor" in list_rd[key_l3].keys()) else None,  # 演员
                            "vod_director":
                                list_rd[key_l3]["vod_director"] if ("vod_director" in list_rd[key_l3].keys()) else None,  # 导演
                            "vod_writer":
                                list_rd[key_l3]["vod_writer"] if ("vod_writer" in list_rd[key_l3].keys()) else None,  # 编剧
                            "vod_behind":
                                list_rd[key_l3]["vod_behind"] if ("vod_behind" in list_rd[key_l3].keys()) else None,  # 幕后
                            "vod_blurb":
                                list_rd[key_l3]["vod_blurb"] if ("vod_blurb" in list_rd[key_l3].keys()) else None,  # 简介
                            "vod_remarks":
                                list_rd[key_l3]["vod_remarks"] if ("vod_remarks" in list_rd[key_l3].keys()) else None,  # 备注
                            "vod_pubdate":
                                list_rd[key_l3]["vod_pubdate"] if ("vod_pubdate" in list_rd[key_l3].keys()) else None,  # 发布日期, 2018-01-20
                            "vod_total":
                                list_rd[key_l3]["vod_total"] if ("vod_total" in list_rd[key_l3].keys()) else None,  # 总集数, 100
                            "vod_serial":
                                list_rd[key_l3]["vod_serial"] if ("vod_serial" in list_rd[key_l3].keys()) else None,  # 连载数, 20
                            "vod_tv":
                                list_rd[key_l3]["vod_tv"] if ("vod_tv" in list_rd[key_l3].keys()) else None,  # 电视频道
                            "vod_weekday":
                                list_rd[key_l3]["vod_weekday"] if ("vod_weekday" in list_rd[key_l3].keys()) else None,  # 节目周期
                            "vod_area":
                                list_rd[key_l3]["vod_area"] if ("vod_area" in list_rd[key_l3].keys()) else None,  # 地区, 大陆
                            "vod_lang":
                                list_rd[key_l3]["vod_lang"] if ("vod_lang" in list_rd[key_l3].keys()) else None,  # 语言, 国语
                            "vod_year":
                                list_rd[key_l3]["vod_year"] if ("vod_year" in list_rd[key_l3].keys()) else None,  # 年份, 2018
                            "vod_version":
                                list_rd[key_l3]["vod_version"] if ("vod_version" in list_rd[key_l3].keys()) else None,  # 资源版本, 高清版
                            "vod_state":
                                list_rd[key_l3]["vod_state"] if ("vod_state" in list_rd[key_l3].keys()) else None,  # 资源类别, 正片, 预告片, 花絮
                            "vod_author":
                                list_rd[key_l3]["vod_author"] if ("vod_author" in list_rd[key_l3].keys()) else None,  # 作者, 作者
                            "vod_jumpurl":
                                list_rd[key_l3]["vod_jumpurl"] if ("vod_jumpurl" in list_rd[key_l3].keys()) else None,  # 跳转URL
                            "vod_isend":
                                list_rd[key_l3]["vod_isend"] if ("vod_isend" in list_rd[key_l3].keys()) else None,  # 已/未完结
                            "vod_lock":
                                list_rd[key_l3]["vod_lock"] if ("vod_lock" in list_rd[key_l3].keys()) else None,  # 锁定/解锁
                            "vod_duration":
                                list_rd[key_l3]["vod_duration"] if ("vod_duration" in list_rd[key_l3].keys()) else None,  # 视频时长
                            "vod_douban_id":
                                list_rd[key_l3]["vod_douban_id"] if ("vod_douban_id" in list_rd[key_l3].keys()) else None,  # 豆瓣ID
                            "vod_douban_score":
                                list_rd[key_l3]["vod_douban_score"] if ("vod_douban_score" in list_rd[key_l3].keys()) else None,  # 豆瓣评分
                            "vod_content":
                                list_rd[key_l3]["vod_content"] if ("vod_content" in list_rd[key_l3].keys()) else None,  # 详情, 介绍
                            "vod_play_from":
                                list_rd[key_l3]["vod_play_from"] if ("vod_play_from" in list_rd[key_l3].keys()) else None,  # 视频资源播放标签, xlm3u8
                            "vod_play_url":
                                list_rd[key_l3]["vod_play_url"] if ("vod_play_url" in list_rd[key_l3].keys()) else None  # 播放资源 url
                        }
                        response_data_list.append(template_data)
                    media_data["page_"+str(gmd_params["pg"])] = response_data_list
                else:
                    return msg(500, "采集格式错误", None)
            else:
                print("获取媒体数据失败, 失败原因: "+response.text)
        result_data["id_"+str(target_info[key]["id"])] = media_data

    return writeStorageFile({"data": result_data}, False)


def getSources():
    resources_info = getCollectAddressInfo()
    for key in range(0, len(resources_info)):
        print("正在获取资源站 "+resources_info[key]["name"]+" 元数据")
        res_target_info = getTargetInfo(resources_info[key]["url"], resources_info[key]["type"])
        if res_target_info["code"] == 200:
            resources_info[key]["data"] = res_target_info["data"]
        else:
            print(json.dumps(res_target_info, encoding="UTF-8"))
    write_data = {"target_info": resources_info}
    if is_update_type_bind:
        data_type_bind = getTypeBind()
        write_data["type_bind"] = data_type_bind
    print("正在尝试写入资源站元数据")
    res_sources_data = writeStorageFile(write_data, False)
    print(res_sources_data["message"])

    # 处理媒体数据
    res_media_data = getMediaData()
    return res_media_data


def postData():
    data = readStorageFile()
    data = data["data"]
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
    type_bind = data["type_bind"]["data"]
    res_data = data["data"]
    del data
    for key in range(0, len(target_info)):  # per resources data
        print("正在处理 "+target_info[key]["name"]+", 共计 "+str(target_info[key]["data"]["total"])+" 条数据")
        temp_res_data = res_data["id_"+str(target_info[key]["id"])]
        for key_l2 in range(1, int(target_info[key]["data"]["page_count"])+1):  # per page data
            for key_l3 in range(0, len(temp_res_data["page_"+str(key_l2)])):  # per data
                temp_l2_rd = temp_res_data["page_"+str(key_l2)][key_l3]
                # 编列数据中所有空字符串数据, 并删除
                # for key_l4, value_l4 in temp_l2_rd.items():
                #     if value_l4 == "":
                #         del temp_l2_rd[key_l4]
                temp_l2_rd = cleanDL(temp_l2_rd)
                type_id_l2rd = calc_md5(target_info[key]["url"])
                type_id_l2rd += "_"+str(temp_l2_rd["type_id"])
                print(type_id_l2rd)
                if type_id_l2rd not in type_bind:
                    for key_l4 in range(0, len(target_info[key]["data"]["class"])):
                        print("名称为 "\
                              +temp_l2_rd["vod_name"]\
                              +" 的媒体数据未绑定类型, 该类型为: "\
                              +target_info[key]["data"]["class"][key_l4]["type_name"])
                        break
                    continue
                temp_l2_rd["type_id"] = type_bind[type_id_l2rd]
                temp_l2_rd["pass"] = site_receive_pass

                time.sleep(sleep_time)  # to sleep
                req_url = site_url+site_receive_address[target_info[key]["mid"]]
                response = requests.post(req_url, params=temp_l2_rd, headers=headers)
                if response.status_code == 200:
                    response_data = json.loads(response.text)
                    if response_data["code"] == 1:
                        print(response_data["msg"])
                    else:
                        print("代码为: "+str(response_data["code"])+", 消息为: "+response_data["msg"])
                else:
                    print(response.text)
    return msg(200, "处理完成", None)


# follow the process
def process():
    res_sources = getSources()
    print(res_sources["message"])
    res_post_data = postData()
    print(res_post_data)


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    process()
    # res_post_data = postData()
    # print(res_post_data)