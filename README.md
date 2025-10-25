# PDF-to-Audiobook-Converter
Converts PDF content into spoken audio

The PDF to Audiobook Converter is a Python-based application that transforms written content from PDF files into spoken audio. It was designed to make reading more accessible and convenient for users who prefer listening, such as students, professionals, and visually impaired individuals. The app extracts text from PDFs using PyMuPDF, converts it into speech through either pyttsx3 (for offline mode) or gTTS (for online mode), and allows users to play or export the result as MP3 files.

The project’s interface, built with Tkinter, provides a simple way to upload files, set reading speed, adjust volume, and choose between different TTS engines. It also integrates pygame for audio playback, offering full control over the listening experience. The program works by first loading and cleaning the extracted text, then processing it in chunks to generate smooth and natural-sounding speech output.

Overall, this project effectively combines text extraction and text-to-speech technologies into one interactive desktop tool. It demonstrates how Python libraries can be used together to enhance accessibility and make digital reading more flexible. Future improvements could include features like advanced voice selection, sentence-based chunking, and mobile support to reach a wider audience.
