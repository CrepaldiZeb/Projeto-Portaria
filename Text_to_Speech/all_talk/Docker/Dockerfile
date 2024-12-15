# Use uma imagem base com suporte a CUDA (ajuste a versão conforme necessário)
FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Defina o ambiente para não interativo, evitando prompts durante a instalação
ENV DEBIAN_FRONTEND=noninteractive

# Atualize os repositórios e instale as dependências necessárias
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tzdata \
        ca-certificates \
        git \
        libaio-dev \
        espeak-ng \
        ffmpeg \
        gcc \
        g++ \
        curl \
        python3-pip && \
    ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Defina o diretório de trabalho dentro do contêiner
WORKDIR /app

# Clone o repositório AllTalk TTS na branch 'feature/easy_install'
RUN git clone -b feature/easy_install https://github.com/CrepaldiZeb/Projeto-Portaria.git . && \
    chmod +x atsetup.sh

# Exponha as portas necessárias
EXPOSE 7851
EXPOSE 7852
EXPOSE 7853

# Defina o comando padrão para iniciar um shell interativo
CMD ["/bin/bash"]
