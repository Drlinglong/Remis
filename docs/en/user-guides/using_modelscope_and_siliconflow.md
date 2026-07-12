# ModelScope and SiliconFlow

Both platforms expose many open models you can pick by cost and quality. Configure them in the **Remis client**, not via install scripts.

## Steps

### 1. Get a token

| Platform | Where (check the official site) |
|----------|----------------------------------|
| **ModelScope** | Access token pages such as [AccessToken](https://modelscope.cn/my/my-accesstoken) |
| **SiliconFlow** | Account / API key area on [siliconflow.cn](https://siliconflow.cn/) |

### 2. Pick a model ID

Browse [ModelScope models](https://modelscope.cn/models) or SiliconFlow’s model list and copy the full model ID/name (prefer chat/instruct models).

### 3. Configure in Remis

1. **Settings → API**  
2. Open **ModelScope** or **SiliconFlow**  
3. Paste token and model ID → **Save**  
4. Select them in **Initial translation** / **Incremental translation**

## Troubleshooting

- **Auth errors**: re-check token in Settings and save again  
- **404 model**: spelling / model still listed on the platform  
- **Rate limits**: lower concurrency/RPM in the job settings  
- **Parse errors**: try a stronger instruct model  

Logs (Windows package): `%APPDATA%\RemisModFactory\logs\remis_backend.log`.

## Related

- [Provider index (ZH)](../../zh/user-guides/provider-setup-index.md)  
- [FAQ](faq.md)  
