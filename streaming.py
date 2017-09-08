#!/usr/bin/python3
"""
grpc와 google API를 이용한 streaming program.
pb 파일은 google-cloud-speech에서 따온다.
현재 main 단에서 180초가 지났을 때 지속적으로 request하도록 하고 있다.

추가제언 )
1. 일단 authentication을 이 안에서 구현해야 한다 - 아직 안되어있다.
2. Hertz에 따른 비교
"""

from google.cloud import speech_v1
import io
import re
import sys
import pyaudio
from six.moves import queue
import select

class MicrophoneStream(object):
    """
    Recording stream을 열어주는 class.
    yield : audio chunk
    """

    """
    rate는 mic 의 sample rate를 받아야한다.
    기본적으로 pyaudio의 sample rate를 높이는 것(44100)과 낮추는 것(16000)의 정확도 차이는 비교해볼 필요가 있다.
    pyaudio와 grpc의 recognitionconfig를 위해서 규정한다.
    """
    def __init__(self,rate,chunk):
        self._rate = rate
        self._chunk = chunk
        # audio data 가 들어갔다가 나올 자료구조(buffer)
        self._buff = queue.Queue()
        # stream이 열렸나 닫혔나를 체크해주는 boolean
        self.closed = True

    """
    with 안에서 돌아갈 함수와 return할 값
    return : self. 즉 초기화한 그 객체를 리턴한다.
    """
    def __enter__(self):
        self._audio_interface= pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

        """Continuously collect data from the audio stream, into the buffer."""
    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)

def listen_print_loop(responses):
    """Iterates through server responses and prints them.
    The responses passed is a generator that will block until a response
    is provided by the server.
    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.
    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.

    loop 내에는
        1. interim transcript
        2. is_result transcript
        3. time offset result 를 담는다.

    현재는 이러한 것들을 print하지만,
    종국에는 MySQL에 INSERT 되어야 한다.
    참고)
    MySQL에서는 list가 곧바로 insert가 되지 않기때문에, list를 customized query string으로 바꾼 후 insertion하는 과정이 필요하다.
    ref) https://stackoverflow.com/questions/8316176/insert-list-into-my-database-using-python
    """
    num_chars_printed = 0
    for response in responses:
        if not response.results:
            continue

        # There could be multiple results in each response.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:

            sys.stdout.write(transcript + overwrite_chars + '\r')
            sys.stdout.flush()

#            print(transcript)
            num_chars_printed = len(transcript)

        else:
            lis = []
            for word_info in result.alternatives[0].words:
                if(len(lis) == 0):
                    lis.append(word_info.start_time.seconds + word_info.start_time.nanos * 1e-9)
                lis.append(word_info.end_time.seconds + word_info.end_time.nanos * 1e-9)

            print(transcript + overwrite_chars)
            print(lis)
            return

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r'\b(exit|quit)\b', transcript, re.I):
                print('Exiting..')
                break

            num_chars_printed = 0

def main(hertz = 16000,lang = 'ko-KR'):

    CHUNK = int(hertz / 10)

    client = speech_v1.SpeechClient()

    # 먼저 streaming config
    config = client.types.RecognitionConfig(
        encoding = client.enums.RecognitionConfig.AudioEncoding.LINEAR16,
        language_code=lang,
        sample_rate_hertz=hertz,
        # for time offset.a
        enable_word_time_offsets=True

    )
    streaming_config = client.types.StreamingRecognitionConfig(config=config,interim_results=True,single_utterance = True)

    with MicrophoneStream(hertz, CHUNK) as stream:
        audio_generator = stream.generator()
        requests  = ( client.types.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

        responses = client.streaming_recognize(
            config = streaming_config,
            requests = requests,
        )

        listen_print_loop(responses)


if __name__== "__main__":
    hertz = int(sys.argv[1])
    while(1):
        try:
            main(hertz,sys.argv[2])
        except:
            continue
