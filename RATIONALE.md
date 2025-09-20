# A Year and a Half of Experimenting with Transcription: What Finally Worked

Over the past year and a half, I kept coming back to the problem of transcribing meetings and calls.  
At first it seemed simple: just take OpenAI’s Whisper and it should work out of the box.  
But in practice it wasn’t that smooth:  
- transcription speed was too slow,  
- recognition quality was inconsistent,  
- sometimes the model would “get stuck” and start repeating the same phrases.  

During this time, I tried several approaches and libraries. Below are my observations and what I ended up with.

---

### Whisper.cpp
👉 [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)  
A C/C++ port of Whisper. It really does speed things up by about ×2 compared to the original implementation.  
But in my tests, one hour of audio still took about one hour to process.

### Faster-Whisper
👉 [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)  
The next step forward. This implementation is based on CTranslate2 and gives another ×2 speed boost on top of whisper.cpp.  
So overall, about ×4 faster than the original Whisper. That’s a noticeable improvement.

### WhisperX
👉 [m-bain/whisperX](https://github.com/m-bain/whisperX)  
This is where the quality really improved. WhisperX uses faster-whisper under the hood but adds:  
- word-level segmentation with precise timestamps,  
- automatic speaker diarization,  
- more robust handling of long contexts.  

After switching to WhisperX, transcription errors became much less frequent, repeated phrases disappeared, and the resulting text was much closer to the original speech.  
As a result, downstream tasks (like summarization with an LLM) produced much better outcomes.

---

### My Wrapper Around WhisperX
I eventually settled on WhisperX and built a simple wrapper to make it more convenient for everyday use.  
What the script does:  
- accepts both audio and video as input,  
- extracts and converts the audio to the required format,  
- applies light loudness normalization,  
- runs WhisperX with optimal parameters,  
- saves a clean `.txt` transcript right next to the input file.  

The result is a one-step tool for transcription.  

Repo: 👉 [arthur-cpp/whx](https://github.com/arthur-cpp/whx)

---

I’m not claiming this is *the* best or only way to do transcription.  
But in my case, WhisperX finally delivered the balance of speed and quality I’d been missing.  
If you’re also looking for ways to improve your transcription pipeline — hopefully this experience will be useful.
