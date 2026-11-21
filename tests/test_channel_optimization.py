import unittest
from unittest.mock import MagicMock
from src.channel import validate_edit, update_video

class OptimizationTest(unittest.TestCase):
    def test_wrong_channel_cannot_be_edited(self):
        yt = MagicMock()
        yt.channels().list().execute.return_value = {'items':[{'id':'wrong','snippet':{'title':'Wrong'}}]}
        with self.assertRaises(RuntimeError): update_video(yt, {'expected_channel_id':'UCA5IqyxUWCJxz-ibknXuZbA'}, {})
        yt.videos().update.assert_not_called()
    def test_description_and_tags_limits(self):
        e = {'id':'8t2BHhbWjKE','title':'What if the Moon disappeared?','description':'x'*4901,'tags':[]}
        with self.assertRaises(ValueError): validate_edit(e)
        e['description']='The Moon shapes Earth’s tides.'; e['tags']=['x'*501]
        with self.assertRaises(ValueError): validate_edit(e)
    def test_category_and_language_preserved(self):
        yt=MagicMock(); yt.channels().list().execute.return_value={'items':[{'id':'target','snippet':{'title':'Makoko'}}]}
        old={'channelId':'target','categoryId':'28','defaultLanguage':'en','title':'Old','description':''}; fresh=dict(old,title='New',description='New description')
        yt.videos().list().execute.side_effect=[{'items':[{'snippet':old}]},{'items':[{'snippet':fresh}]}]
        update_video(yt,{'expected_channel_id':'target'},{'id':'8t2BHhbWjKE','title':'New','description':'New description','tags':['Moon']})
        body=yt.videos().update.call_args.kwargs['body']
        self.assertEqual(body['snippet']['categoryId'],'28'); self.assertEqual(body['snippet']['defaultLanguage'],'en'); self.assertNotIn('status',body)
