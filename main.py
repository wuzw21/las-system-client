import os
import psutil,nvidia_smi
import netifaces
import requests
import urllib.parse
from config import BASE_IP,BASE_PORT,BASE_URL
import time
import functools,threading,subprocess

def download_url(url : str, local_filename) :
    response = requests.get(url)
    # 检查请求是否成功
    if response.status_code == 200:
        # 打开本地文件，以二进制写入模式打开
        with open(local_filename, 'wb') as f:
            # 将请求的内容写入到本地文件中
            f.write(response.content)
        # print(f"文件已保存到本地: {local_filename}")
        return 1
    else:
        # print("下载失败")
        return 0
def get_mac_address():
    for interface in netifaces.interfaces():
        if interface == 'lo':
            continue
        mac = netifaces.ifaddresses(interface).get(netifaces.AF_LINK)
        if mac:
            return mac[0]['addr']

mac = get_mac_address()
token = urllib.parse.quote(mac)
current_directory = os.path.dirname(os.path.abspath(__file__))
task_lists = []

def solve(id : int, task_info : dict) :
    # prepare
    print(f'start doing task{id}!')
    task_lists.append(task_id)
    start_time = time.time()
    data = {'task_id' : id , 'token' : token, 'type' : 2}
    response = requests.post(BASE_URL + '/task/update_status', data=data)
    data = response.json()
    task_url = task_info.get('task_url')
    task_path = 'task_data/{}'.format(id)
    if not os.path.exists(task_path) :
        os.makedirs(task_path)
    else :
        os.system('rm -rf {}'.format(task_path))
        os.makedirs(task_path)
    zip_path = task_path + '/script.zip'
    download_url(task_url, zip_path)
    unzip_path = 'task_data/{}/script'.format(id)
    os.system('unzip {} -d {}'.format(zip_path, unzip_path))
    os.system('chmod 777 {}/run.sh'.format(unzip_path))
    command = 'sh {}/run.sh'.format(unzip_path)
    # 执行命令并等待其完成
    result = subprocess.run(command, shell=True, cwd=current_directory)
    # 获取命令的退出状态码
    exit_code = result.returncode
    last_time = time.time()
    task_lists.remove(id)
    print(f'end doing task{id}!')
    if exit_code == 0:
        data = {'task_id' : id , 'token' : token, 'type' : 3 , 'time_length' : last_time - start_time}
        response = requests.post(BASE_URL + '/task/update_status', data=data)
        data = response.json()
        return 1
    else :
        error_message = result.stderr.decode('utf-8')
        # print("错误信息:", error_message)
        data = {'task_id' : id , 'token' : token, 'type' : 0 , 'error_text' : error_message}
        response = requests.post(BASE_URL + '/task/update_status', data=data)
        data = response.json()
        return 0
def make_component(type : str, name : str, text : str, units : list) :
    return {
        'type' : type,
        'name' : name,
        'text' : text,
        'resources' : [{'text' : unit.get('text'), 'value' : unit.get('value')} for unit in units]
    }
    
def get_resource() :
    components = []
    # GET CPU total,allocated,used
    # 获取 CPU 的总核心数
    total_cores = psutil.cpu_count(logical=False)  # 逻辑核心数（默认）

    # 获取已分配核心数和使用的核心数
    allocated_cores = psutil.cpu_count(logical=True)  # 逻辑核心数
    cpu_usage = psutil.cpu_percent(interval=1)  # 每个核心的使用率列表

    # print("CPU 总核心数:", total_cores)
    # print("CPU 已分配核心数:", allocated_cores)
    # print("CPU 使用情况:", cpu_usage)
    components.append(make_component('PROCESSOR', 'CPU', 'CPU', [{'text' : '总核心数', 'value' : total_cores}, {'text' : '已分配核心数', 'value' : allocated_cores}, {'text' : '使用情况', 'value' : cpu_usage}]))
    # GET Disk total,allocated,used
    disk = psutil.disk_usage('/')
    # GET Network total,allocated,used
    # GET Memory
    
    # 初始化 NVIDIA Management Library
    nvidia_smi.nvmlInit()

    # 获取 GPU 数量
    device_count = nvidia_smi.nvmlDeviceGetCount()

    # print("GPU 数量:", device_count)

    # 获取每个 GPU 的详细信息
    for i in range(device_count):
        handle = nvidia_smi.nvmlDeviceGetHandleByIndex(i)
        gpu_name = nvidia_smi.nvmlDeviceGetName(handle)
        gpu_memory = nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
        gpu_utilization = nvidia_smi.nvmlDeviceGetUtilizationRates(handle)

        # print(f"GPU {i}:")
        # print(f"  Name: {gpu_name}")
        # print(f"  Memory Total: {gpu_memory.total / 1024**2} MB")
        # print(f"  Memory Used: {gpu_memory.used / 1024**2} MB")
        # print(f"  Memory Free: {gpu_memory.free / 1024**2} MB")
        # print(f"  GPU Utilization: {gpu_utilization.gpu} %")
        components.append(make_component('PROCESSOR', f'GPU {i}', 'gpu_name', [{'text' : 'Memory Total', 'value' : gpu_memory.total / 1024**2}, {'text' : 'Memory Used', 'value' : gpu_memory.used / 1024**2}, {'text' : 'Memory Free', 'value' : gpu_memory.free / 1024**2}, {'text' : 'GPU Utilization', 'value' : gpu_utilization.gpu}]))

    # 获取内存使用情况
    memory_info = psutil.virtual_memory()

    # 打印内存总量
    total_memory = memory_info.total
    # print("总内存:", total_memory / (1024*1024), "MB")

    # 打印可用内存
    available_memory = memory_info.available
    # print("可用内存:", available_memory / (1024*1024), "MB")

    # 打印已使用内存
    used_memory = memory_info.used
    # print("已使用内存:", used_memory / (1024*1024), "MB")
    components.append(make_component('STORAGE', 'Memory', 'Memory', [{'text' : 'total', 'value' : total_memory / (1024*1024)}, {'text' : 'free', 'value' : available_memory / (1024*1024)}, {'text' : 'used', 'value' : used_memory / (1024*1024)}]))

    # 获取磁盘使用情况信息
    disk_info = psutil.disk_usage('/')
    # 打印磁盘容量
    total_disk_space = disk_info.total
    # print("磁盘总容量:", total_disk_space / (1024*1024*1024), "GB")
    # 打印磁盘可用空间
    free_disk_space = disk_info.free
    # print("可用磁盘空间:", free_disk_space / (1024*1024*1024), "GB")
    disk_io_counters = psutil.disk_io_counters()
    current_disk_io = disk_io_counters.read_bytes + disk_io_counters.write_bytes
    # print("当前的磁盘IO开销:", current_disk_io / (1024*1024), "MB")
    components.append(make_component('STORAGE', 'Disk', 'Disk', [{'text' : 'total', 'value' : total_disk_space / (1024*1024*1024)}, {'text' : 'free', 'value' : free_disk_space / (1024*1024*1024)}, {'text' : 'IO', 'value' : current_disk_io}]))    
    return components
# 将字节对象转换为字符串
def bytes_to_string(data):
    if isinstance(data, bytes):
        return data.decode('utf-8')
    elif isinstance(data, dict):
        return {key: bytes_to_string(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [bytes_to_string(item) for item in data]
    else:
        return data

# 将浮点数转换为标准浮点数格式
def convert_float(data):
    if isinstance(data, dict):
        return {key: convert_float(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_float(item) for item in data]
    elif isinstance(data, str):
        try:
            return float(data)
        except ValueError:
            return data
    else:
        return data
    
if __name__ == "__main__":
    # print("MAC Address:", mac)
    response = requests.get(BASE_URL + "/node/search_token?token={}".format(token))
    data : dict= response.json()
    if data.get('code') == -2 :
        print('New Node!')
        data = {'op_type' : 0,'token': token}
        response = requests.post(BASE_URL + '/node/upload', data=data)
        data = response.json()
        # print(data)
    else :
        print("Log in!")
        pass
    node_info : dict = data.get('node_info')
    node_id = int(node_info.get('id'))
    while True:
        time.sleep(1)   # 暂停1秒钟
        resource = get_resource()
        data : dict = {'token':token ,'resource' : resource}
        data = bytes_to_string(data)
        data = convert_float(data)
        response = requests.post(BASE_URL + '/node/update', json= data)
        data = response.json()
        response = requests.get(BASE_URL + '/node/get_task_order?node_id={}'.format(node_id))
        data : dict = response.json()
        tasks : dict = data.get('tasks',[])
        for task in tasks :
            task_id = int(task.get('type',0))
            if task_id == 1 and task_id not in task_lists :
                task_func = functools.partial(solve, task_id, task)
                t = threading.Thread(target=task_func)
                t.detech = True
                t.start()
        print(f'Node {node_id} is running!')
