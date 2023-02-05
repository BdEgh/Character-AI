import json
import aiohttp


class CharacterAI:
    def __init__(self):
        self.token = None

    def get_headers(self, auth=False):
        headers = {'Content-Type': 'application/json', 'User-Agent': 'Chrome/79'}
        if auth:
            if self.token is None:
                raise Exception("Not authenticated")
            headers['Authorization'] = f'Token {self.token}'
        return headers

    async def get_query(self, url, auth=False):
        headers = self.get_headers(auth=auth)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                else:
                    raise Exception(resp.status)

    async def post_complicated_query(self, url, body, auth=False):
        headers = self.get_headers(auth=auth)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers) as resp:
                if resp.status == 200:
                    data = b''
                    async for chunk in resp.content.iter_chunks():
                        data += chunk[0]
                        end = chunk[0].find(b'\n')
                        if end != -1:
                            end = len(chunk[0]) - end
                            yield json.loads(data[:-end].decode().strip())
                            data = data[-end:]

    async def post_query(self, url, body, auth=False):
        headers = self.get_headers(auth=auth)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data

    async def authenticate(self, token):
        url = 'https://beta.character.ai/dj-rest-auth/auth0/'
        body = {'access_token': token}
        data = await self.post_query(url, body, auth=False)
        self.token = data.get('key')

    async def get_categories(self):
        url = 'https://beta.character.ai/chat/character/categories/'
        return await self.get_query(url, True)

    async def get_user_config(self):
        url = 'https://beta.character.ai/chat/config/'
        return await self.get_query(url, True)

    async def get_user(self):
        url = 'https://beta.character.ai/chat/user/'
        return await self.get_query(url, True)

    # async def get_featured(self):
    #     url = 'https://beta.character.ai/chat/characters/featured/'
    #     return await self.get_query(url, True)

    # async def get_characters_by_categories(self, curated=False):
    #     categories = 'curated_categories' if curated else 'categories'
    #     url = f'https://beta.character.ai/chat/{categories}'
    #     return await self.get_query(url, True)

    async def get_character_info(self, character_id):
        url = 'https://beta.character.ai/chat/character/info/'
        body = {'external_id': character_id}
        return await self.post_query(url, body, True)

    async def create_new_chat(self, character_id):
        body = {'character_external_id': character_id,
                'history_external_id': None}
        url = 'https://beta.character.ai/chat/history/create/'
        data = await self.post_query(url, body, True)
        return AIChat(self, character_id, data)

    async def continue_chat(self, character_id, history_id):
        url = 'https://beta.character.ai/chat/history/continue/'
        body = {'character_external_id': character_id,
                'history_external_id': history_id}
        data = await self.post_query(url, body, True)
        return AIChat(self, character_id, data)

    async def continue_last_or_create_chat(self, character_id):
        url = 'https://beta.character.ai/chat/history/continue/'
        body = {'character_external_id': character_id,
                'history_external_id': None}
        data = await self.post_query(url, body, True)
        if data.get('status') == 'No Such History':
            return await self.create_new_chat(character_id)
        return AIChat(self, character_id, data)


class AIChat:
    def __init__(self, client, character_id, continue_body):
        self.client = client
        self.character_id = character_id
        self.external_id = continue_body.get('external_id')
        ai = next(filter(lambda participant: not participant['is_human'], continue_body['participants']))
        self.ai_id = ai['user']['username']

    async def get_history(self):
        url = 'https://beta.character.ai/chat/history/msgs/user/?history_external_id='
        async with self.client.get_query(f'{url}{self.external_id}') as resp:
            data = await resp.json()
            return data

    async def send_message(self, message):
        body = {
            "history_external_id": self.external_id,
            "character_external_id": self.character_id,
            "text": message,
            "tgt": self.ai_id,
            "ranking_method": "random",
            "faux_chat": False,
            "staging": False,
            "model_server_address": None,
            "override_prefix": None,
            "override_rank": None,
            "rank_candidates": None,
            "filter_candidates": None,
            "prefix_limit": None,
            "prefix_token_limit": None,
            "livetune_coeff": None,
            "stream_params": None,
            "enable_tti": True,
            "initial_timeout": None,
            "insert_beginning": None,
            "translate_candidates": None,
            "stream_every_n_steps": 16,
            "chunks_to_pad": 8,
            "is_proactive": False
        }
        url = 'https://beta.character.ai/chat/streaming/'
        async for answer in self.client.post_complicated_query(url, body, True):
            if answer is not None:
                yield answer['replies'][0], answer['src_char']['participant']['name'], answer['avatar_file_name']
