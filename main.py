import feedparser
import time
import os
import re
import pytz
from datetime import datetime
import yagmail
import requests
import markdown
import json
import shutil
from urllib.parse import urlparse
from multiprocessing import Pool,  Manager


def get_rss_info(feed_url, index, rss_info_list):
    result = {"result": []}
    request_success = False
    # 如果请求出错,则重新请求,最多五次
    for i in range(3):
        if(request_success == False):
            try:
                headers = {
                    # 设置用户代理头(为狼披上羊皮)
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36",
                    "Content-Encoding": "gzip"
                }
                # 三次分别设置8, 16, 24秒钟超时
                feed_url_content = requests.get(
                    feed_url,  timeout=(i+1)*8, headers=headers).content
                feed = feedparser.parse(feed_url_content)
                feed_author = feed['feed']['title']
                feed_entries = feed["entries"]
                feed_entries_length = len(feed_entries)
                print("==feed_url=>>", feed_url,
                      "==len=>>", feed_entries_length)
                for entrie in feed_entries[0: feed_entries_length-1]:
                    title = entrie["title"]
                    link = entrie["link"]
                    date = time.strftime(
                        "%Y-%m-%d", entrie["published_parsed"])

                    title = title.replace("\n", "")
                    title = title.replace("\r", "")

                    result["result"].append({
                        "feed_author": feed_author,
                        "feed_url": feed_url,
                        "title": title,
                        "link": link,
                        "date": date
                    })
                request_success = True
            except Exception as e:
                print(feed_url+"第+"+str(i)+"+次请求出错==>>", e)
                pass
        else:
            pass

    rss_info_list[index] = result["result"]
    print("本次爬取==》》", feed_url, "<<<===", index, result["result"])
    # 剩余数量
    remaining_amount = 0

    for tmp_rss_info_atom in rss_info_list:
        if(isinstance(tmp_rss_info_atom, int)):
            remaining_amount = remaining_amount + 1

    print("当前进度 | 剩余数量", remaining_amount, "已完成==>>",
          len(rss_info_list)-remaining_amount)
    return result["result"]


def send_mail(email, title, contents):
    # 判断secret.json是否存在
    user = ""
    password = ""
    host = ""
    try:
        if(os.environ["USER"]):
            user = os.environ["USER"]
        if(os.environ["PASSWORD"]):
            password = os.environ["PASSWORD"]
        if(os.environ["HOST"]):
            host = os.environ["HOST"]
    except:
        print("无法获取github的secrets配置信息,开始使用本地变量")
        if(os.path.exists(os.path.join(os.getcwd(), "secret.json"))):
            with open(os.path.join(os.getcwd(), "secret.json"), 'r') as load_f:
                load_dict = json.load(load_f)
                user = load_dict["user"]
                password = load_dict["password"]
                host = load_dict["host"]
                # print(load_dict)
        else:
            print("无法获取发件人信息")

    # 连接邮箱服务器
    # yag = yagmail.SMTP(user=user, password=password, host=host)
    yag = yagmail.SMTP(user=user, password=password, host=host)
    # 发送邮件
    yag.send(email, title, contents)


def replace_readme():
    # 读取EditREADME.md
    print("replace_readme")
    new_num = 0
    markdown_str = ''
    with open(os.path.join(os.getcwd(), "EditREADME.md"), 'r') as load_f:
        edit_readme_md = load_f.read()
        before_info_list = re.findall(
            r'\{\{latest_content\}\}.*\[订阅地址\]\(.*\)', edit_readme_md)
        # 使用进程池进行数据获取，获得rss_info_list
        before_info_list_len = len(before_info_list)
        rss_info_list = Manager().list(range(before_info_list_len))
        print('before_info_list==》', before_info_list)

        # 创建一个最多开启8进程的进程池
        po = Pool(8)
        for index, before_info in enumerate(before_info_list):
            # 获取link
            link = re.findall(r'\[订阅地址\]\((.*)\)', before_info)[0]
            po.apply_async(get_rss_info, (link, index, rss_info_list))

        # 关闭进程池,不再接收新的任务,开始执行任务
        po.close()

        # 主进程等待所有子进程结束
        po.join()
        print("----rss_info_list----", rss_info_list)
        for index, before_info in enumerate(before_info_list):
            print('before_info', before_info)
            # 获取link
            link = re.findall(r'\[订阅地址\]\((.*)\)', before_info)[0]
            # 生成超链接
            rss_info = rss_info_list[index]
            print('rss_info', rss_info)
            if len(rss_info) > 0:
                markdown_str = markdown_str + '\r\n' + '\r\n' + \
                    f'###  {rss_info[0]["feed_author"]}' + '\r\n' + '\r\n'
                for rss_info_atom in rss_info:
                    if (rss_info_atom["date"] == datetime.today().strftime("%Y-%m-%d")):
                        new_num += 1
                        onelink_el = f'<a target=_blank rel=nofollow href="{rss_info_atom["link"]}" >{rss_info_atom["title"]}-{rss_info_atom["date"]}</a><br/>'
                        markdown_str += onelink_el
                        print('onelink_el', onelink_el)
                markdown_str += '\r\n'
            markdown_str += '\r\n'
    post_datetime = datetime.fromtimestamp(
        int(time.time()), pytz.timezone('Asia/Shanghai')).strftime('%Y%m%d%H%M%S')
    markdown_str = f'<h1>{post_datetime}</h1><br/>共{new_num}篇文章' + \
        '\r\n' + markdown_str
    print('markdown_str', markdown_str)
    return markdown_str

# 将README.md复制到docs中


def cp_readme_md_to_docs():
    post_datetime = datetime.fromtimestamp(
        int(time.time()), pytz.timezone('Asia/Shanghai')).strftime('%Y%m%d%H%M%S')
    shutil.copyfile(os.path.join(os.getcwd(), "README.md"),
                    os.path.join(os.getcwd(), "docs", f"{post_datetime}.md"))


def get_email_list():
    email_list = []
    with open(os.path.join(os.getcwd(), "tasks.json"), 'r') as load_f:
        load_dic = json.load(load_f)
        for task in load_dic["tasks"]:
            email_list.append(task["email"])
    return email_list

# 创建opml订阅文件


def create_opml():
    result = ""
    result_v1 = ""
    # <outline text="CNET News.com" description="Tech news and business reports by CNET News.com. Focused on information technology, core topics include computers, hardware, software, networking, and Internet media." htmlUrl="http://news.com.com/" language="unknown" title="CNET News.com" type="rss" version="RSS2" xmlUrl="http://news.com.com/2547-1_3-0-5.xml"/>

    with open(os.path.join(os.getcwd(), "EditREADME.md"), 'r') as load_f:
        edit_readme_md = load_f.read()

        # 将信息填充到opml_info_list
        opml_info_text_list = re.findall(
            r'.*\{\{latest_content\}\}.*\[订阅地址\]\(.*\).*', edit_readme_md)

        for opml_info_text in opml_info_text_list:

            # print('==', opml_info_text)

            opml_info_text_format_data = re.match(
                r'\|(.*)\|(.*)\|(.*)\|(.*)\|.*\[订阅地址\]\((.*)\).*\|', opml_info_text)

            # print("data==>>", opml_info_text_format_data)

            # print("总信息", opml_info_text_format_data[0].strip())
            # print("编号==>>", opml_info_text_format_data[1].strip())
            # print("text==>>", opml_info_text_format_data[2].strip())
            # print("description==>>", opml_info_text_format_data[3].strip())
            # print("data004==>>", opml_info_text_format_data[4].strip())
            print('##', opml_info_text_format_data[2].strip())
            print(opml_info_text_format_data[3].strip())
            print(opml_info_text_format_data[5].strip())

            opml_info = {}
            opml_info["text"] = opml_info_text_format_data[2].strip()
            opml_info["description"] = opml_info_text_format_data[3].strip()
            opml_info["htmlUrl"] = opml_info_text_format_data[5].strip()
            opml_info["title"] = opml_info_text_format_data[2].strip()
            opml_info["xmlUrl"] = opml_info_text_format_data[5].strip()

            # print('opml_info==>>', opml_info);

            opml_info_text = '<outline  text="{text}" description="{description}" htmlUrl="{htmlUrl}" language="unknown" title="{title}" type="rss" version="RSS2" xmlUrl="{xmlUrl}"/>'

            opml_info_text_v1 = '      <outline text="{title}" title="{title}" type="rss"  \n            xmlUrl="{xmlUrl}" htmlUrl="{htmlUrl}"/>'

            opml_info_text = opml_info_text.format(
                text=opml_info["text"],
                description=opml_info["description"],
                htmlUrl=opml_info["htmlUrl"],
                title=opml_info["title"],
                xmlUrl=opml_info["xmlUrl"]
            )

            opml_info_text_v1 = opml_info_text_v1.format(
                htmlUrl=opml_info["htmlUrl"],
                title=opml_info["title"],
                xmlUrl=opml_info["xmlUrl"]
            )

            result = result + opml_info_text + "\n"

            result_v1 = result_v1 + opml_info_text_v1 + "\n"

    zhaoolee_github_garss_subscription_list = ""
    with open(os.path.join(os.getcwd(), "rss-template-v2.txt"), 'r') as load_f:
        zhaoolee_github_garss_subscription_list_template = load_f.read()
        GMT_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
        date_created = datetime.utcnow().strftime(GMT_FORMAT)
        date_modified = datetime.utcnow().strftime(GMT_FORMAT)
        zhaoolee_github_garss_subscription_list = zhaoolee_github_garss_subscription_list_template.format(
            result=result, date_created=date_created, date_modified=date_modified)
        # print(zhaoolee_github_garss_subscription_list);

    # 将内容写入
    with open(os.path.join(os.getcwd(), "zhaoolee_github_garss_subscription_list_v2.opml"), 'w') as load_f:
        load_f.write(zhaoolee_github_garss_subscription_list)

    zhaoolee_github_garss_subscription_list_v1 = ""
    with open(os.path.join(os.getcwd(), "rss-template-v1.txt"), 'r') as load_f:
        zhaoolee_github_garss_subscription_list_template = load_f.read()
        zhaoolee_github_garss_subscription_list_v1 = zhaoolee_github_garss_subscription_list_template.format(
            result=result_v1)
        # print(zhaoolee_github_garss_subscription_list_v1);

    # 将内容写入
    with open(os.path.join(os.getcwd(), "zhaoolee_github_garss_subscription_list_v1.opml"), 'w') as load_f:
        load_f.write(zhaoolee_github_garss_subscription_list_v1)


def add_sidebar():
    post_datetime = datetime.fromtimestamp(
        int(time.time()), pytz.timezone('Asia/Shanghai')).strftime('%Y%m%d%H%M%S')
    new_md = f'* [{post_datetime}]({post_datetime}) \r\n'
    with open('./docs/_sidebar.md', 'r') as f:
        old_md = f.read()
    with open('./docs/_sidebar.md', 'w') as f:
        old_md = f.write(new_md + old_md)


def main():
    # 要先获取分类，没有的话，需要新建，这种方式好方便，不用解析数据库，但解析数据库貌似才是最好的
    # 等会儿抽时间看数据库的内容
    create_opml()
    readme_md = replace_readme()
    # file = open("./README.md", 'w')
    # file.write(readme_md)
    # file.close()
    cp_readme_md_to_docs()
    add_sidebar()
    email_list = get_email_list()
    print('readme_md', readme_md)
    # 填充统计时间
    post_datetime = datetime.fromtimestamp(
        int(time.time()), pytz.timezone('Asia/Shanghai')).strftime('%Y%m%d%H%M%S')
    try:
        send_mail(email_list, f"{post_datetime} 文章汇总", readme_md)
    except Exception as e:
        print("==邮件设信息置错误===》》", e)


if __name__ == "__main__":
    main()
