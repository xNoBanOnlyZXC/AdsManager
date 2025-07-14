<div align="center">
    <h1>Ads Manager</h1>
    <img src="https://github.com/user-attachments/assets/9096b677-2089-4aac-918a-b980e607f17b"  width="200" height="200"><br>
    Ad-managing tool for chat.
    <p>Made by <bold>~$ sudo++</bold></p>
    <img alt="code size" src="https://img.shields.io/github/languages/code-size/xnobanonlyzxc/adsmanager?style=for-the-badge">
    <img alt="repo stars" src="https://img.shields.io/github/stars/xnobanonlyzxc/adsmanager?style=for-the-badge">
    <img alt="repo stars" src="https://img.shields.io/github/commit-activity/w/xnobanonlyzxc/adsmanager?style=for-the-badge">
</div>

---
The bot automatically keeps the specified advertisement at the bottom of the chat (up to N number of advertisement messages).

The bot has a notification system - if a user (who is not an administrator) sends /start to the bot, all administrators will receive a notification with the name, username and user ID.

The bot remembers the entire advertising post (pyrogram) or a post with 1 image (telebot) saving the data to the ads.json file

The bot remembers its advertising posts, i.e. after restarting the bot, it will still know what its last advertising posts were (last.dict)

---
### How to use?
1. Fill fields: `API_ID`, `API_HASH` (for pyrogram variant), `TOKEN`, `CHAT_ID`, `ADMINS`
2. Run bot.
### What it can do now?

#### ✨ Admin Management

  * `/admin <user_id>`: Add a user to the administrator list.
      * Example: `/admin 123456789`
  * `/unadmin <user_id>`: Remove a user from the administrator list.
      * Example: `/unadmin 123456789`
  * `/adminme` (TESTMODE only): Add yourself to the administrator list.
  * `/unadminme` (TESTMODE only): Remove yourself from the administrator list.

#### 🗑️ Message Management

  * `/del <chat_id> <message_id>`: Delete a specific message in the designated chat.
      * Example: `/del -1001234567890 54321`
  * `/get <chat_id> <message_id>`: Retrieve message data in JSON format.
      * Example: `/get -1001234567890 54321`

#### 📣 Advertisement Management

  * `/ad` (reply to a message): Add a new advertisement.
      * Use this command by replying to a message containing text or a photo. You can include a referrer (`@username` or `+7XXXXXXXXXX`) and a comment (`# Your comment`) in the last lines of the message.
      * Example message for an ad:
        ```
        Your ad text here.
        # Your comment for the phone number
        @your_username or +79991234567
        ```
  * `/ads`: Show a list of all active advertisements.
      * From here, you can manage ads: view, modify, delete, and edit referrers and comments.

#### 💬 Chat Management

  * `/chats`: Manage active and inactive chats where the bot is present. You can activate/deactivate chats for ad display, leave chats, or remove them from the list.

#### 🔄 Other

  * `/clear`: Clear your current state. This is useful if you're in the middle of editing an ad and want to cancel the action.

---
**Pyrofix** - important part of the code, includes Pyrogram code fixes.
