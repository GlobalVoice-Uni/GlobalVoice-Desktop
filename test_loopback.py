"""PoC de enumeracao e gravacao de audio via WASAPI Loopback no Windows."""

import wave
import pyaudiowpatch as pyaudio


def list_and_record_loopback(duration_s: int = 5, output_wav: str = "teste_loopback.wav") -> None:
    p = pyaudio.PyAudio()

    try:
        # 1. Localiza a API de host WASAPI nativa do Windows
        wasapi_info = None
        for i in range(p.get_host_api_count()):
            api = p.get_host_api_info_by_index(i)
            if api["type"] == pyaudio.paWASAPI:
                wasapi_info = api
                break

        if wasapi_info is None:
            print("[-] Erro: Host API WASAPI nao encontrada neste sistema.")
            return

        print(f"[+] WASAPI encontrada no indice {wasapi_info['index']}: {wasapi_info['name']}")

        # 2. Obtem os alto-falantes padrao de saida
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        print(f"[+] Dispositivo padrao de saida: {default_speakers['name']}")

        # 3. Localiza o dispositivo de loopback correspondente aos alto-falantes
        loopback_device = None
        if not default_speakers.get("isLoopbackDevice", False):
            for dev in p.get_loopback_device_info_generator():
                if default_speakers["name"] in dev["name"]:
                    loopback_device = dev
                    break
        else:
            loopback_device = default_speakers

        if loopback_device is None:
            print("[-] Nao foi possivel encontrar o canal de loopback para a saida padrao.")
            print("[i] Dispositivos de loopback disponiveis:")
            for dev in p.get_loopback_device_info_generator():
                print(f"    - [{dev['index']}] {dev['name']}")
            return

        print(f"[+] Dispositivo de Loopback selecionado: [{loopback_device['index']}] {loopback_device['name']}")

        # 4. Parametros do stream (usar os padroes nativos do dispositivo)
        channels = int(loopback_device["maxInputChannels"])
        sample_rate = int(loopback_device["defaultSampleRate"])
        frames_per_buffer = 1024

        print(f"[i] Gravando {duration_s} segundos de audio do sistema...")
        print(f"    Canais: {channels} | Sample Rate: {sample_rate} Hz")
        print("    >> Toque algum som agora (video no YouTube, musica, etc.) <<")

        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            input=True,
            input_device_index=loopback_device["index"],
            frames_per_buffer=frames_per_buffer,
        )

        frames = []
        total_chunks = int((sample_rate / frames_per_buffer) * duration_s)

        for _ in range(total_chunks):
            data = stream.read(frames_per_buffer)
            frames.append(data)

        print("[+] Gravacao concluida!")

        stream.stop_stream()
        stream.close()

        # 5. Salva em arquivo WAV para auditoria/validacao
        with wave.open(output_wav, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(sample_rate)
            wf.writeframes(b"".join(frames))

        print(f"[+] Amostra gravada com sucesso em: {output_wav}")

    finally:
        p.terminate()


if __name__ == "__main__":
    list_and_record_loopback()