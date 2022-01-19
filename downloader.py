import subprocess, requests, re, multiprocessing, datetime, os

PACKAGE_PATH = "./packages"
VARSION_HTML_TAG = "js-versionLink"
WORKER_NUM = 5


def handle_package(packageName):
    res = []
    versionsPage=requests.get(f"https://pkg.go.dev/{packageName}","tab=versions")
    for line in versionsPage.text.splitlines():
        if VARSION_HTML_TAG in line:
            res.append(f"go get {packageName}@{re.search('>.+<', line).group(0)[1:-1]}")
    return res

#start docker images that will download the packages
def start_workers():
    workers = []
    for index in range(WORKER_NUM):
        process = subprocess.Popen(f"docker run --net godownloadnet --rm --name goworker-{index} -d -e GO111MODULE=on -e GOPROXY=http://athens:3000 golang:1.17 tail -f /dev/null".split(), stdout=subprocess.PIPE)
        _, error = process.communicate()
        if error != None:
            print(error)
        workers.append(f"goworker-{index}")
    return workers

def download_package(worker, packages):
    for package in packages:
        print(f"docker exec {worker} {package}".split())
        process = subprocess.Popen(f"docker exec {worker} {package}".split(), stdout=subprocess.PIPE)
        _, error = process.communicate()
        if error != None:
            print(error)
    

def main():
    # Gather the modules and their deps for download
    filepath = 'packages.txt'
    packages = []
    with open(PACKAGE_PATH) as fp:
        line = fp.readline()
        while line:
            print(line)
            packages.extend(handle_package(line.strip()))
            line = fp.readline()

    print("finishe gathering packages")
    # Start Up Athenes
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
    athenesStartUpScript = f"""docker network create godownloadnet
    mkdir -p {os.getenv('PWD')}/downloaded-packages/{timestamp}
    docker run -d --net godownloadnet --name athens --rm -p 3000:3000 -v {os.getenv('PWD')}/downloaded-packages/{timestamp}:/var/lib/athens -e ATHENS_DISK_STORAGE_ROOT=/var/lib/athens -e ATHENS_STORAGE_TYPE=disk gomods/athens"""
    # until curl -s -f -o /dev/null "http://127.0.0.1:3000"; do; sleep 1; done 

    for cmd in athenesStartUpScript.splitlines():
        print("executing:" + cmd)
        if cmd:
            process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
            _, error = process.communicate()
            if error != None:
                print(error)
                return

    print("finished setting up Athenes")
    workers = start_workers()
    print(workers)
    print("worker were started")

    # run
    jobs = []
    packagesListOffset = len(packages)/len(workers)
    for index in range(len(workers)):
        p = multiprocessing.Process(target=download_package, args=(workers[index],packages[int(packagesListOffset * index):int(packagesListOffset * (index+1) )],))
        jobs.append(p)
        p.start()

    for procces in jobs:
        procces.join()

    print("waiting for workers to finish")
    # cleanup 
    process = subprocess.Popen("docker stop athens".split(), stdout=subprocess.PIPE)
    _, error = process.communicate()
    if error != None:
        print(error)
    

    for worker in workers:
        process = subprocess.Popen(f"docker stop {worker}".split(), stdout=subprocess.PIPE)
        _, error = process.communicate()
        if error != None:
            print(error) 

    process = subprocess.Popen("docker network rm godownloadnet".split(), stdout=subprocess.PIPE)
    _, error = process.communicate()
    if error != None:
        print(error)

    print("finished downloading")

if __name__ == '__main__':
    main()