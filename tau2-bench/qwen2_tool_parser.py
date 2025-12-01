import json
import re
from typing import Dict, List, Sequence, Union

import partial_json_parser
from partial_json_parser.core.options import Allow

from vllm.entrypoints.openai.protocol import (ChatCompletionRequest,
                                              DeltaFunctionCall, DeltaMessage,
                                              DeltaToolCall,
                                              ExtractedToolCallInformation,
                                              FunctionCall, ToolCall)
from vllm.entrypoints.openai.tool_parsers.abstract_tool_parser import (
    ToolParser, ToolParserManager)
from vllm.logger import init_logger
from vllm.transformers_utils.tokenizer import AnyTokenizer, MistralTokenizer
from vllm.utils import random_uuid

logger = init_logger(__name__)


@ToolParserManager.register_module("qwen2")
class Qwen2ToolParser(ToolParser):

    def __init__(self, tokenizer: AnyTokenizer):
        super().__init__(tokenizer)

        if isinstance(self.model_tokenizer, MistralTokenizer):
            logger.error(
                "Detected Mistral tokenizer when using a Qwen2.5 model")
            self.model_tokenizer = self.model_tokenizer.tokenizer

        self.current_tool_name_sent: bool = False
        self.prev_tool_call_arr: List[Dict] = []
        self.current_tool_id: int = -1
        self.streamed_args_for_tool: List[str] = [
        ]  # map what has been streamed for each tool so far to a list

        self.tool_call_start_token: str = "<tool_call>"
        self.tool_call_end_token: str = "</tool_call>"

        self.tool_call_regex = re.compile(
            r"<tool_call>(.*?)</tool_call>", re.DOTALL)
        self.scratch_pad_regex = re.compile(
            r"<scratch_pad>(.*?)</scratch_pad>", re.DOTALL)

        if not self.model_tokenizer:
            raise ValueError(
                "The model tokenizer must be passed to the ToolParser "
                "constructor during construction.")
        self.tool_call_start_token_id = self.vocab.get(
            self.tool_call_start_token)
        self.tool_call_end_token_id = self.vocab.get(self.tool_call_end_token)
        if (self.tool_call_start_token_id is None
                or self.tool_call_end_token_id is None):
            raise RuntimeError(
                "Qwen2.5 Tool parser could not locate tool call start/end "
                "tokens in the tokenizer!")

    def extract_tool_calls(
        self,
        model_output: str,
        request: ChatCompletionRequest,
    ) -> ExtractedToolCallInformation:

        # sanity check; avoid unnecessary processing
        if self.tool_call_start_token not in model_output:
            return ExtractedToolCallInformation(tools_called=False,
                                                tool_calls=[],
                                                content=model_output)

        else:

            try:
                # find all tool calls between "<tool_call>" and "</tool_call>"
                # the other is None
                function_call_strs = (
                    self.tool_call_regex.findall(model_output))

                # load the JSON, and then use it to build the Function and
                # Tool Call
                raw_function_calls = json.loads(function_call_strs[0])

                tool_calls = [
                    ToolCall(
                        type="function",
                        function=FunctionCall(
                            name=function_call["tool_name"],
                            # function call args are JSON but as a string
                            arguments=json.dumps(function_call["parameters"], ensure_ascii=False)
                        )
                    )
                    for function_call in raw_function_calls
                ]

                content = model_output[:model_output.
                                       find(self.tool_call_start_token)]
                return ExtractedToolCallInformation(
                    tools_called=True,
                    tool_calls=tool_calls,
                    content=content if content else None)

            except Exception:
                logger.exception(
                    "Error in extracting tool call from response.")
                return ExtractedToolCallInformation(tools_called=False,
                                                    tool_calls=[],
                                                    content=model_output)

# for streamed parsing
def extract_tool_calls_streaming(
        self,
        previous_text: str,
        current_text: str,
        delta_text: str,
        previous_token_ids: Sequence[int],
        current_token_ids: Sequence[int],
        delta_token_ids: Sequence[int],
        request: ChatCompletionRequest,
    ) -> Union[DeltaMessage, None]:

    pass