import json
import os
import re
import tempfile
import uuid

from PyQt5.QtCore import QUrl, QObject, pyqtSignal, QEventLoop, QCoreApplication, QThread, QElapsedTimer
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


class PingThread(QThread):
    pingSignal = pyqtSignal(str, float)

    def __init__(self, name: str, url: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.host = None
        self.url = None
        self.name = None
        self.reSet(name, url)

    def reSet(self, name: str, url: str) -> None:
        self.name = name
        self.url = url
        self.host = self.url.split("/")

    def ping(self) -> float:
        timer = QElapsedTimer()
        timer.start()
        try:
            nam = QNetworkAccessManager()
            request = QNetworkRequest(QUrl(self.url))

            reply = nam.get(request)
            loop = QEventLoop()
            reply.finished.connect(loop.quit)
            loop.exec_()
        except Exception:
            return float('inf')
        time = timer.elapsed()
        return time

    def run(self) -> None:
        responseTime = self.ping()
        self.pingSignal.emit(self.name, responseTime)


class SourceManager(QObject):
    quickSource = pyqtSignal(str, float)

    def __init__(self, sources: dict, current: str = None, parent=None):
        super().__init__(parent)
        if not isinstance(sources, dict):
            raise TypeError
        if not sources:
            raise ValueError
        self.sources = sources
        # 第一个的key
        self.currentSource = list(sources.keys())[
            0] if current is None else current
        self.speedData = {}
        self.threads = []

    @property
    def sources(self):
        return self.__sources

    @sources.setter
    def sources(self, sources: dict):
        if not isinstance(sources, dict):
            raise TypeError
        if not sources:
            raise ValueError
        for key in sources:
            sources[key]['url'] = sources[key]['url'].strip('/')
        self.__sources = sources
        self.currentSource = list(sources.keys())[0]

    @property
    def currentSource(self):
        """
        当前使用的源
        """
        return self.__currentSource

    @property
    def token(self) -> str:
        return self.__sources[self.currentSource]['token']

    @property
    def tokenUrl(self) -> str:
        if self.currentSource == "gitee":
            return f'?access_token={self.token}'
        else:
            return ""

    @currentSource.setter
    def currentSource(self, currentSource: str):
        """
        设置当前使用的源

        Args:
            currentSource (str): 源名称

        Raises:
            ValueError: 如果currentSource不在sources中
        """
        if currentSource not in self.sources:
            raise ValueError
        self.__currentSource = currentSource

    @property
    def currentSourceUrl(self):
        return self.sources[self.currentSource]['url']

    def checkSourceSpeed(self):
        """
        检查所有源的速度,并发射quickSource(name:str,time:float)信号来获取最快的源，所有的源的速度可以通过speedData属性获取
        """
        self.threads.clear()
        self.speedData = {}
        for source in self.sources:
            thread = PingThread(source, self.sources[source]['url'])
            thread.pingSignal.connect(self.__pingSignal)
            self.threads.append(thread)
            thread.start()

    def __pingSignal(self, url: str, responseTime: float):
        self.speedData[url] = responseTime
        if len(self.speedData) == len(self.sources):
            quickTime = float('inf')
            quickKey = ''
            for key, value in self.speedData.items():
                if value < quickTime:
                    quickTime = value
                    quickKey = key
            self.quickSource.emit(quickKey, quickTime)


class ReleaseInfo:
    def __init__(self, dataJson: dict, versionReStr: str) -> None:
        self.tag_name = dataJson['tag_name'] if re.search(
            versionReStr, dataJson['tag_name']) else dataJson['name']
        self.body = dataJson['body']
        self.html_url = dataJson['html_url'] if 'html_url' in dataJson else ""
        m_assert = dataJson['assets'][0]
        self.assets_name = m_assert['name']
        self.assets_content_type = m_assert['content_type'] if 'content_type' in m_assert else ""
        self.assets_size = m_assert['size'] if 'size' in m_assert else 0
        self.assets_download_count = m_assert['download_count'] if 'download_count' in m_assert else ""
        self.assets_created_at = m_assert['created_at'] if 'created_at' in m_assert else ""
        self.assets_browser_download_url = m_assert['browser_download_url']


class GitHub(QObject):
    isNeedUpdateAsyncSignal = pyqtSignal(bool)
    latestReleaseAsyncSignal = pyqtSignal(ReleaseInfo)
    releasesAsyncSignal = pyqtSignal(list)
    downloadReleaseAsyncStartSignal = pyqtSignal(ReleaseInfo)
    downloadReleaseAsyncProgressSignal = pyqtSignal(int, int)
    downloadReleaseAsyncFinishSignal = pyqtSignal(str)
    errorSignal = pyqtSignal(str)

    def __init__(self, sourceManager: SourceManager, version: str, versionReStr: str,
                 parent=None):
        """
        :param sourceManager: 一个SourceManager实例，提供了多个github api的url
        :param version: 当前的版本号
        :param versionReStr: 一个正则表达式串，用于从github的release中，提取版本号
        :param parent: 一个QObject实例，父对象
        """
        super().__init__(parent)
        self.__sourceManager = sourceManager
        self.__version = version
        self.__versionReStr = versionReStr
        self.__replyDict = {}

    @property
    def sourceManager(self) -> SourceManager:
        return self.__sourceManager

    @sourceManager.setter
    def sourceManager(self, sourceManager: SourceManager) -> None:
        if self.__sourceManager is not None:
            self.__sourceManager.deleteLater()
        self.__sourceManager = sourceManager
        self.__sourceManager.setParent(self)

    @property
    def version(self) -> str:
        return self.__version

    @version.setter
    def version(self, version: str) -> None:
        self.__version = version

    @property
    def versionReStr(self) -> str:
        return self.__versionReStr

    @versionReStr.setter
    def versionReStr(self, versionReStr: str) -> None:
        self.__versionReStr = versionReStr

    @property
    def latestReleaseUrl(self) -> str:
        """
        获取最新的release的url
        """
        return f'{self.sourceManager.currentSourceUrl}/releases/latest{self.sourceManager.tokenUrl}'

    @property
    def releasesUrl(self) -> str:
        """
        获取所有release的url
        """
        return f'{self.sourceManager.currentSourceUrl}/releases{self.sourceManager.tokenUrl}'

    def isNeedUpdate(self, isAsync: bool = True) -> bool | str | None:
        """
        判断是否需要更新

        :param isAsync: 是否异步
        :return: bool :如果不是异步，返回True表示需要更新，False表示不需要更新，None表示网络错误 \n
                 str: 如果是异步，返回一个当前请求的唯一标识，并发射isNeedUpdateAsyncSignal信号
        """

        nam, request = self.__createRequest(self.latestReleaseUrl)
        reply = nam.get(request)
        reply.setObjectName(str(uuid.uuid1()))
        self.__replyDict[reply.objectName()] = reply
        if not isAsync:
            loop = QEventLoop()
            reply.finished.connect(loop.quit)
            loop.exec()
            if reply.error() != QNetworkReply.NoError:
                self.error(reply.errorString())
                return None
            dataStr = reply.readAll().data().decode('utf-8')
            self.__replyDict.pop(reply.objectName())
            reply.deleteLater()
            return self.__isNeedUpdate(dataStr)
        else:
            nam.finished.connect(self.__isNeedUpdateAsync)
            return reply.objectName()

    def __isNeedUpdate(self, dataStr: str) -> bool:
        release = ReleaseInfo(json.loads(dataStr), self.versionReStr)
        return self.compareVersion(release.tag_name) == '>'

    def __isNeedUpdateAsync(self, reply: QNetworkReply):
        if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
            pass
        elif reply.error() != QNetworkReply.NoError:
            self.error(reply.errorString())
        else:
            self.isNeedUpdateAsyncSignal.emit(
                self.__isNeedUpdate(reply.readAll().data().decode('utf-8')))
        self.__replyDict.pop(reply.objectName())
        reply.deleteLater()

    def latestRelease(self, isAsync: bool = True) -> ReleaseInfo | str | None:
        """
        获取最新的release

        :param isAsync: 是否异步
        :return: bool :如果不是异步，返回一个Release实例
                 str: 如果是异步，返回一个当前请求的唯一标识，并发射latestReleaseAsyncSignal信号
        """

        nam, request = self.__createRequest(self.latestReleaseUrl)
        reply = nam.get(request)
        reply.setObjectName(str(uuid.uuid1()))
        self.__replyDict[reply.objectName()] = reply
        if not isAsync:
            loop = QEventLoop()
            reply.finished.connect(loop.quit)
            loop.exec()
            if reply.error() != QNetworkReply.NoError:
                self.error(reply.errorString())
                return None
            dataStr = reply.readAll().data().decode('utf-8')
            self.__replyDict.pop(reply.objectName())
            reply.deleteLater()
            return ReleaseInfo(json.loads(dataStr), self.versionReStr)
        else:
            nam.finished.connect(self.__lastReleaseAsync)
            return reply.objectName()

    def __lastReleaseAsync(self, reply: QNetworkReply):
        if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
            pass
        elif reply.error() != QNetworkReply.NoError:
            self.error(reply.errorString())
        else:
            self.latestReleaseAsyncSignal.emit(
                ReleaseInfo(json.loads(reply.readAll().data().decode('utf-8')), self.versionReStr))
        self.__replyDict.pop(reply.objectName())
        reply.deleteLater()

    def releases(self, isAsync: bool = True) -> list | str | None:
        """
        获取所有release

        :param isAsync: 是否异步
        :return: list :如果不是异步，返回一个Release实例的列表
                 str: 如果是异步，返回一个当前请求的唯一标识，并发射releasesAsyncSignal信号
        """
        nam, request = self.__createRequest(self.releasesUrl)
        reply = nam.get(request)
        reply.setObjectName(str(uuid.uuid1()))
        self.__replyDict[reply.objectName()] = reply
        if not isAsync:
            loop = QEventLoop()
            reply.finished.connect(loop.quit)
            loop.exec()
            if reply.error() != QNetworkReply.NoError:
                self.error(reply.errorString())
                return None
            dataStr = reply.readAll().data().decode('utf-8')
            self.__replyDict.pop(reply.objectName())
            reply.deleteLater()
            return self.__releases(dataStr)
        else:
            nam.finished.connect(self.__releasesAsync)
            return reply.objectName()

    def __releases(self, dataStr: str) -> list | None:
        return [ReleaseInfo(x, self.versionReStr) for x in json.loads(dataStr)]

    def __releasesAsync(self, reply: QNetworkReply):
        if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
            pass
        elif reply.error() != QNetworkReply.NoError:
            self.error(reply.errorString())
        else:
            releases = self.__releases(reply.readAll().data().decode('utf-8'))
            self.releasesAsyncSignal.emit(releases)
        self.__replyDict.pop(reply.objectName(), None)
        reply.deleteLater()

    def downloadRelease(self, release: ReleaseInfo) -> str:
        """
        下载release

        :param release: 需要下载的release
        :return: 一个当前请求的唯一标识
        """
        self.downloadReleaseAsyncStartSignal.emit(release)
        nam, request = self.__createRequest(
            release.assets_browser_download_url)
        reply = nam.get(request)
        reply.setObjectName(str(uuid.uuid1()))
        self.__replyDict[reply.objectName()] = reply
        reply.downloadProgress.connect(self.__downloadProgress)
        reply.finished.connect(lambda: self.__saveFile(release))
        return reply.objectName()

    def __createRequest(self, url: str) -> tuple[QNetworkAccessManager, QNetworkRequest]:
        """
        创建一个QNetworkAccessManager和QNetworkRequest
        Parameters
        ----------
        url
            请求的url
        Returns
        -------
        tuple[QNetworkAccessManager, QNetworkRequest]
            一个QNetworkAccessManager和QNetworkRequest
        """
        nam = QNetworkAccessManager(self)
        request = QNetworkRequest(QUrl(url))
        request.setAttribute(
            QNetworkRequest.Attribute.FollowRedirectsAttribute, True)
        return nam, request

    def __downloadProgress(self, bytesReceived: int, bytesTotal: int):
        """
        用于触发downloadReleaseAsyncProgressSignal信号

        :param bytesReceived: 已经下载的字节数
        :param bytesTotal: 需要下载的总字节数
        """
        self.downloadReleaseAsyncProgressSignal.emit(bytesReceived, bytesTotal)

    def __saveFile(self, release: ReleaseInfo):
        """
        从reply中读取数据并根据release.assets_name保存到临时文件夹

        :param release: 需要保存的release
        :return: None
        """
        reply: QNetworkReply = self.sender()
        if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
            pass
        elif reply.error() != QNetworkReply.NoError:
            self.error(reply.errorString())
        else:
            # 临时文件夹
            tempDir = tempfile.gettempdir()
            path = os.path.join(tempDir, release.assets_name)
            # 判断是否存在
            if os.path.exists(path):
                os.remove(path)
            with open(path, 'wb') as f:
                f.write(reply.readAll())
            self.downloadReleaseAsyncFinishSignal.emit(path)
        if reply.objectName() in self.__replyDict:
            self.__replyDict.pop(reply.objectName())
            reply.deleteLater()

    def compareVersion(self, v2: str) -> str:
        """和当前版本比较

        Args:
            v2 (str): 需要比较的版本

        Returns:
            str: "<","=" or ">"
        """
        v = re.findall(self.__versionReStr, self.__version)
        if len(v) == 0:
            return '<'
        v1 = re.findall(self.__versionReStr, v2)
        if len(v1) == 0:
            return '<'
        v1 = v1[0]
        v = v[0]
        vList = v.split('.')
        v1list = v1.split('.')
        for i in range(len(vList)):
            if int(vList[i]) > int(v1list[i]):
                return '<'
            elif int(vList[i]) < int(v1list[i]):
                return '>'
        return '='

    def error(self, errorStr: str):
        self.errorSignal.emit(errorStr)

    def closeAllRequest(self):
        """关闭所有的请求"""
        keys = list(self.__replyDict.keys())
        for key in keys:
            self.__replyDict[key].abort()
        self.__replyDict.clear()

    def closeRequest(self, identification: str):
        """关闭单个请求

        Args:
            identification (str): 请求的唯一标识
        """
        if identification in self.__replyDict:
            self.__replyDict[identification].abort()
            self.__replyDict.pop(identification)

    @staticmethod
    def removeAllTempFile(fileNameRe: str):
        """删除临时文件夹中的安装包文件"""
        tempDir = tempfile.gettempdir()
        # 按照项目名称正则匹配
        for file in os.listdir(tempDir):
            if re.match(fileNameRe, file):
                os.remove(os.path.join(tempDir, file))

    def removeDownloadFile(self):
        """删除下载的文件"""
        GitHub.removeAllTempFile(f".*{self.__repo}.*")


if __name__ == '__main__':
    app = QCoreApplication([])
    data = {
        "Github": "https://api.github.com/repos/eee555/Metasweeper",
        "gitee": "https://api.gitee.com/repos/ee55/Metasweeper",
    }
    github = GitHub(SourceManager(data, "gitee"), "3.1.9", "(\d+\.\d+\.\d+)")
    github.releasesAsyncSignal.connect(lambda x: print(x))
    github.releases()
    # manager = SourceManager(data)
    # manager.quickSource.connect(lambda x,y:print(x,y))
    # manager.checkSourceSpeed()
    app.exec_()
