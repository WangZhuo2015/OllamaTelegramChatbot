# Ollama Telegram Chatbot

![GitHub license](https://img.shields.io/github/license/WangZhuo2015/OllamaTelegramChatbot)
![GitHub stars](https://img.shields.io/github/stars/WangZhuo2015/OllamaTelegramChatbot?style=social)
![GitHub forks](https://img.shields.io/github/forks/WangZhuo2015/OllamaTelegramChatbot?style=social)
![GitHub issues](https://img.shields.io/github/issues/WangZhuo2015/OllamaTelegramChatbot)

This project is a simple Telegram bot built using `ollama` and `aiogram`. The bot is capable of handling user queries and generating responses.
## Features

- **Proxy Support (Optional)**: Configurable HTTP/Socks proxy for connecting to Telegram if needed.
- **Real-time Response Generation**: Provides instant feedback during response generation.

## Planned Features

- [X]  **User Identity Control**: Implement authentication and authorization to manage user access and permissions.
- [X]  **Chat History Persistence**: Store chat history in a database to enable session continuity and data recovery.
- [ ]  **User Archiving**: Enable users to archive and retrieve previous chat sessions.
- [X]  **Request Queue Management**: Queue user requests to manage load and ensure fair processing.
- [ ]  **Containerization**: Deploy the bot using Docker to simplify deployment and scalability.
- [X]  **Model Switching**: Allow users to switch between different models for varied interactions.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/WangZhuo2015/OllamaTelegramChatbot.git
   cd OllamaTelegramChatbot
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables**:
   Create a `.env` file in the root directory with the following variables:
   ```env
   TOKEN=your-telegram-bot-token
   PROXY_URL=optional-proxy-url
   INITMODEL=your-initial-model
   ```

   remove `PROXY_URL` if you don't need a proxy.

4. **Run the Bot**:
   ```bash
   python main.py
   ```

## Usage

Once the bot is running, you can interact with it on Telegram. The bot will respond to commands and text messages
according to its configured model.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE.md) file for more details.