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


# 输入feed_url, index， 输出rss_info_list
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


def replace_readme(sourceFile):
    # 读取EditREADME.md
    print("replace_readme")
    new_num = 0
    markdown_str = ''
    with open(os.path.join(os.getcwd(), sourceFile), 'r') as load_f:
        # edit_readme_md = load_f.read()
        # before_info_list = re.findall(
        #     r'\{\{latest_content\}\}.*\[订阅地址\]\(.*\)', edit_readme_md)
        xml_str = load_f.read()
        before_info_list = re.findall(
            r'xmlUrl=\"([\s\S]*?)\"', xml_str)  
        print('before_info_list',before_info_list)   
        # 使用进程池进行数据获取，获得rss_info_list
        before_info_list_len = len(before_info_list)
        rss_info_list = Manager().list(range(before_info_list_len))
        print('before_info_list==》', before_info_list)

        # 创建一个最多开启8进程的进程池
        po = Pool(8)
        for index, link in enumerate(before_info_list):
            print('link', link)
            po.apply_async(get_rss_info, (link, index, rss_info_list))
        # 关闭进程池,不再接收新的任务,开始执行任务
        po.close()
        # 主进程等待所有子进程结束
        po.join()
        
        print("----rss_info_list----", rss_info_list)
        for index, link in enumerate(before_info_list):
            print('link', link)
            # 生成超链接
            rss_info = rss_info_list[index]
            print('rss_info', rss_info)
            if len(rss_info) > 0:
                markdown_str = markdown_str + '\r\n' + '\r\n' + \
                    f'###  {rss_info[0]["feed_author"]}' + '\r\n' + '\r\n'
                for rss_info_atom in rss_info:
                    if (rss_info_atom["date"] == datetime.today().strftime("%Y-%m-%d")):
                        new_num += 1
                        onelink_el = f'<a target=_blank rel=nofollow href="{rss_info_atom["link"]}" >{rss_info_atom["title"]}-{rss_info_atom["date"]}</a><br/><br/>'
                        markdown_str += onelink_el
                        print('onelink_el', onelink_el)
                markdown_str += '\r\n'
                markdown_str += '\r\n'
            markdown_str += '\r\n'
            markdown_str += '\r\n'
    post_datetime = datetime.fromtimestamp(
        int(time.time()), pytz.timezone('Asia/Shanghai')).strftime('%Y%m%d%H%M%S')
    markdown_str = f'<h1>{post_datetime}</h1><br/>共{new_num}篇文章' + \
        '\r\n' + markdown_str
    print('markdown_str', markdown_str)
    return markdown_str

# 将README.md复制到docs中
def cp_readme_md_to_docs(filename):
    shutil.copyfile(os.path.join(os.getcwd(), "./docs/Temp.md"),
                    os.path.join(os.getcwd(), "docs", f"{filename}.md"))
    shutil.copyfile(os.path.join(os.getcwd(), "./docs/_sidebar.md"),
                    os.path.join(os.getcwd(), "docs", f"README.md"))


def get_email_list():
    email_list = []
    with open(os.path.join(os.getcwd(), "tasks.json"), 'r') as load_f:
        load_dic = json.load(load_f)
        for task in load_dic["tasks"]:
            email_list.append(task["email"])
    return email_list


def add_sidebar(new_md):
    with open('./docs/_sidebar.md', 'r') as f:
        old_md = f.read()
    with open('./docs/_sidebar.md', 'w') as f:
        old_md = f.write(new_md + old_md)


def main():
    sourceFileList = ['./docs/web3_150.xml','./docs/xiaomu.opml']
    namelist = ['web3_150','xiaomu']
    index = 0
    add_sidebar('\r\n')
    add_sidebar('\r\n')
    add_sidebar('\r\n')
    for sourceFile in sourceFileList:
        readme_md = replace_readme(sourceFile)
        name = namelist[index]
        file = open("./docs/Temp.md", 'w')
        file.write(readme_md)
        file.close()
        # 填充统计时间
        post_datetime = datetime.fromtimestamp(
        int(time.time()), pytz.timezone('Asia/Shanghai')).strftime('%Y%m%d%H%M%S')
        filename = f"{post_datetime}-{name}"
        new_md = f'* [{filename}]({filename}) \r\n'
        add_sidebar(new_md)
        cp_readme_md_to_docs(filename)
        email_list = get_email_list()
        print('readme_md', readme_md)
        try:
            send_mail(email_list, f"{filename}", readme_md)
        except Exception as e:
            print("==邮件设信息置错误===》》", e)
        index = index + 1    


if __name__ == "__main__":
    main()
