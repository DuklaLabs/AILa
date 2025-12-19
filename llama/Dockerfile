FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

RUN apt update && apt install -y \
    git build-essential cmake python3 python3-pip

WORKDIR /opt
RUN git clone https://github.com/ggerganov/llama.cpp
WORKDIR /opt/llama.cpp
RUN make LLAMA_CUDA=1

EXPOSE 8000
CMD ["./server", "-m", "/models/model.gguf", "--host", "0.0.0.0"]
