<div align="center">
    <h1>Ads Manager</h1>
    <img src="https://github.com/user-attachments/assets/3abe87c8-db50-4155-aaf5-ddcdd9b51754"  width="200" height="200"><br>
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
### Commands list
`/ad` (in response to a message) - add an ad message (maximum 1 image)

`/ads` - list of ads (maximum - 3)

`/this` (in response to a message, telebot only) - will send this.txt with full details of the message that was responded to

---
**Pyrofix** - important part of the code, includes Pyrogram code fixes.
