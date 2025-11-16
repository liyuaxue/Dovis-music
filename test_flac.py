import soundfile as sf
import sounddevice as sd
import requests
import tempfile
import os


def test_flac_playback():
    # 测试FLAC播放
    test_url = "https://m701.music.126.net/20251112144905/624fdd1fda6bdd1e990a3e34a3469fd6/jdymusic/obj/wo3DlMOGwrbDjj7DisKw/59380389564/6208/bdff/c609/48528ac72450220810d50149cfc2e004.flac"

    # 下载文件
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(test_url, stream=True, headers=headers)
    temp_file = os.path.join(tempfile.gettempdir(), "test.flac")

    with open(temp_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    print(f"文件下载完成: {temp_file}")

    # 使用soundfile读取
    try:
        data, samplerate = sf.read(temp_file)
        print(f"音频信息: 采样率={samplerate}Hz, 形状={data.shape}")

        # 使用sounddevice播放
        print("开始播放...")
        sd.play(data, samplerate)
        sd.wait()  # 等待播放完成
        print("播放完成!")

    except Exception as e:
        print(f"播放失败: {e}")

    # 清理
    try:
        os.remove(temp_file)
    except:
        pass


if __name__ == "__main__":
    test_flac_playback()