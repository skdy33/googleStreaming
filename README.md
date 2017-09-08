# googleStreaming

## 필요사항 
* Pyaudio 설치
* [grpc 설치](https://grpc.io/blog/installation)
* [google-cloud-speech  사용](https://pypi.python.org/pypi/google-cloud-speech)
* [google speech API SDK 설치, auth 필요](https://cloud.google.com/speech/docs/getting-started)

## documentation
* [google cloud speech reference](https://cloud.google.com/speech/reference/rpc/google.cloud.speech.v1#google.cloud.speech.v1.Speech.StreamingRecognize)

## 기타
현재 streaming은 interim이 출력되고, interim이 끝날 시 언어모델이 반영된 결과물이 나옵니다. <br>
또한 각 단어의 시작 시간이 나오고 <br>
코드는 terminate 됩니다.<br>

필요한 기능은 1시간, 혹은 2시간 짜리의 지속적인 recording이며 <br>
pause, stop, restart기능을 구현하여야 합니다. <br>

이 부분은 논의하며, 대개 제가 구현하게 될 것입니다. <br>
하지만 서버단에기능을 추가함에 있어, 아셔야할 것 같아 말씀을 드리는 것입니다.
