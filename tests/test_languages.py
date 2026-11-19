import unittest

from translation_quality.languages import code_from_filename, code_from_text, display_name


class FilenameTests(unittest.TestCase):
    CASES = {
        "AI_Human_Evaluation_Form_Client_ES_US.xlsm": "es-US",
        "AI_Human_Evaluation_Form_Client_JP_US.xlsm": "ja-US",
        "AI_Human_Evaluation_Form_Client_zh-CN.XLSM": "zh-CN",
        "AI_Human_Evaluation_Form_Client_th_TH (Campaign page).xlsm": "th-TH",
        "AI_Human_Evaluation_Form_Client_DE.xlsm": "de",
        "AI_Human_Evaluation_Form_Client_ro_RO_2.XLSM": "ro-RO",
        "AI_Human_Evaluation_Form_Client_pt_BR.xlsm": "pt-BR",
        "AI_Human_Evaluation_Form_Client_es-419.xlsx": "es-419",
        "AI_Human_Evaluation_Form_Final.xlsx": None,
    }

    def test_codes_from_file_names(self):
        for name, expected in self.CASES.items():
            with self.subTest(name=name):
                self.assertEqual(code_from_filename(name), expected)


class TextTests(unittest.TestCase):
    def test_codes_from_form_fields(self):
        self.assertEqual(code_from_text("Vietnamese (vi-VN)"), "vi-VN")
        self.assertEqual(code_from_text("fr-FR"), "fr-FR")
        self.assertEqual(code_from_text("zh_CN"), "zh-CN")
        self.assertEqual(code_from_text("Korean"), "ko")
        self.assertEqual(code_from_text("Italian (Italy)"), "it")
        self.assertEqual(code_from_text("Chinese (Simplified)"), "zh-CN")
        self.assertIsNone(code_from_text("Website project"))
        self.assertIsNone(code_from_text(""))


class DisplayTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(display_name("es-US"), "Spanish (US)")
        self.assertEqual(display_name("pt-BR"), "Portuguese (Brazil)")
        self.assertEqual(display_name("zh-CN"), "Chinese (Simplified)")
        self.assertEqual(display_name("zh-TW"), "Chinese (Traditional)")
        self.assertEqual(display_name("ko-KR"), "Korean")
        self.assertEqual(display_name("de"), "German")
        self.assertEqual(display_name("xx-YY"), "xx-YY")


if __name__ == "__main__":
    unittest.main()
