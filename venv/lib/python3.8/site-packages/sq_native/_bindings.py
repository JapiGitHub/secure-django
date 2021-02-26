# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
# 
#     https://www.sqreen.io/terms.html
# 
# /!\ This file is generated. DO NOT EDIT /!\
from ctypes import *

from ._ffi import _lib, _PWArgs, PW_LOG_FUNC

PWI_INVALID = 0
PWI_SIGNED_NUMBER = 1 << 0
PWI_UNSIGNED_NUMBER = 1 << 1
PWI_STRING = 1 << 2
PWI_ARRAY = 1 << 3
PWI_MAP = 1 << 4

PW_INPUT_TYPE = c_int

PWHandle = c_void_p

PWAddContext = c_void_p

PWArgs = _PWArgs

PWD_PARSING_JSON = 0
PWD_PARSING_RULE = 1
PWD_PARSING_RULE_FILTER = 2
PWD_OPERATOR_VALUE = 3
PWD_DUPLICATE_RULE = 4
PWD_PARSING_FLOW = 5
PWD_PARSING_FLOW_STEP = 6
PWD_MEANINGLESS_STEP = 7
PWD_DUPLICATE_FLOW = 8
PWD_DUPLICATE_FLOW_STEP = 9
PWD_STEP_HAS_INVALID_RULE = 10

PW_DIAG_CODE = c_int

PW_ERR_INTERNAL = -6
PW_ERR_TIMEOUT = -5
PW_ERR_INVALID_CALL = -4
PW_ERR_INVALID_RULE = -3
PW_ERR_INVALID_FLOW = -2
PW_ERR_NORULE = -1
PW_GOOD = 0
PW_MONITOR = 1
PW_BLOCK = 2

PW_RET_CODE = c_int

PWL_TRACE = 0
PWL_DEBUG = 1
PWL_INFO = 2
PWL_WARN = 3
PWL_ERROR = 4
_PWL_AFTER_LAST = 5

PW_LOG_LEVEL = c_int

class PWConfig(Structure):
    _fields_ = [
        ("maxArrayLength", c_uint64),
        ("maxMapDepth", c_uint64),
    ]

_pw_init = _lib.pw_init
_pw_init.restype = c_bool
_pw_init.argtypes = [c_char_p, c_char_p, POINTER(PWConfig), POINTER(c_char_p)]
def pw_init(ruleName, wafRule, config, errors):
    # type: (Any, Any, Any, Any) -> c_bool
    return _pw_init(ruleName, wafRule, config, errors)  # type: ignore

class PWRet(Structure):
    _fields_ = [
        ("action", PW_RET_CODE),
        ("data", c_char_p),
        ("perfData", c_char_p),
        ("perfTotalRuntime", c_uint32),
        ("perfCacheHitRate", c_uint32),
    ]

_pw_run = _lib.pw_run
_pw_run.restype = PWRet
_pw_run.argtypes = [c_char_p, PWArgs, c_uint64]
def pw_run(ruleName, parameters, timeLeftInUs):
    # type: (Any, Any, Any) -> PWRet
    return _pw_run(ruleName, parameters, timeLeftInUs)  # type: ignore

_pw_clearRule = _lib.pw_clearRule
_pw_clearRule.restype = None
_pw_clearRule.argtypes = [c_char_p]
def pw_clearRule(ruleName):
    # type: (Any) -> None
    return _pw_clearRule(ruleName)  # type: ignore

_pw_clearAll = _lib.pw_clearAll
_pw_clearAll.restype = None
_pw_clearAll.argtypes = []
def pw_clearAll():
    # type: () -> None
    return _pw_clearAll()  # type: ignore

_pw_initH = _lib.pw_initH
_pw_initH.restype = PWHandle
_pw_initH.argtypes = [c_char_p, POINTER(PWConfig), POINTER(c_char_p)]
def pw_initH(wafRule, config, errors):
    # type: (Any, Any, Any) -> PWHandle
    return _pw_initH(wafRule, config, errors)  # type: ignore

_pw_runH = _lib.pw_runH
_pw_runH.restype = PWRet
_pw_runH.argtypes = [PWHandle, PWArgs, c_uint64]
def pw_runH(wafHandle, parameters, timeLeftInUs):
    # type: (Any, Any, Any) -> PWRet
    return _pw_runH(wafHandle, parameters, timeLeftInUs)  # type: ignore

_pw_clearRuleH = _lib.pw_clearRuleH
_pw_clearRuleH.restype = None
_pw_clearRuleH.argtypes = [PWHandle]
def pw_clearRuleH(wafHandle):
    # type: (Any) -> None
    return _pw_clearRuleH(wafHandle)  # type: ignore

_pw_initAdditive = _lib.pw_initAdditive
_pw_initAdditive.restype = PWAddContext
_pw_initAdditive.argtypes = [c_char_p]
def pw_initAdditive(ruleName):
    # type: (Any) -> PWAddContext
    return _pw_initAdditive(ruleName)  # type: ignore

_pw_initAdditiveH = _lib.pw_initAdditiveH
_pw_initAdditiveH.restype = PWAddContext
_pw_initAdditiveH.argtypes = [PWHandle]
def pw_initAdditiveH(powerwafHandle):
    # type: (Any) -> PWAddContext
    return _pw_initAdditiveH(powerwafHandle)  # type: ignore

_pw_runAdditive = _lib.pw_runAdditive
_pw_runAdditive.restype = PWRet
_pw_runAdditive.argtypes = [PWAddContext, PWArgs, c_uint64]
def pw_runAdditive(context, newArgs, timeLeftInUs):
    # type: (Any, Any, Any) -> PWRet
    return _pw_runAdditive(context, newArgs, timeLeftInUs)  # type: ignore

_pw_clearAdditive = _lib.pw_clearAdditive
_pw_clearAdditive.restype = None
_pw_clearAdditive.argtypes = [PWAddContext]
def pw_clearAdditive(context):
    # type: (Any) -> None
    return _pw_clearAdditive(context)  # type: ignore

_pw_freeDiagnotics = _lib.pw_freeDiagnotics
_pw_freeDiagnotics.restype = None
_pw_freeDiagnotics.argtypes = [c_char_p]
def pw_freeDiagnotics(errors):
    # type: (Any) -> None
    return _pw_freeDiagnotics(errors)  # type: ignore

_pw_freeReturn = _lib.pw_freeReturn
_pw_freeReturn.restype = None
_pw_freeReturn.argtypes = [PWRet]
def pw_freeReturn(output):
    # type: (Any) -> None
    return _pw_freeReturn(output)  # type: ignore

class PWVersion(Structure):
    _fields_ = [
        ("major", c_uint16),
        ("minor", c_uint16),
        ("patch", c_uint16),
    ]

_pw_getVersion = _lib.pw_getVersion
_pw_getVersion.restype = PWVersion
_pw_getVersion.argtypes = []
def pw_getVersion():
    # type: () -> PWVersion
    return _pw_getVersion()  # type: ignore

_pw_setupLogging = _lib.pw_setupLogging
_pw_setupLogging.restype = c_bool
_pw_setupLogging.argtypes = [PW_LOG_FUNC, PW_LOG_LEVEL]
def pw_setupLogging(cb, min_level):
    # type: (Any, Any) -> c_bool
    return _pw_setupLogging(cb, min_level)  # type: ignore

_pw_getInvalid = _lib.pw_getInvalid
_pw_getInvalid.restype = PWArgs
_pw_getInvalid.argtypes = []
def pw_getInvalid():
    # type: () -> PWArgs
    return _pw_getInvalid()  # type: ignore

_pw_createStringWithLength = _lib.pw_createStringWithLength
_pw_createStringWithLength.restype = PWArgs
_pw_createStringWithLength.argtypes = [c_char_p, c_uint64]
def pw_createStringWithLength(string, length):
    # type: (Any, Any) -> PWArgs
    return _pw_createStringWithLength(string, length)  # type: ignore

_pw_createString = _lib.pw_createString
_pw_createString.restype = PWArgs
_pw_createString.argtypes = [c_char_p]
def pw_createString(string):
    # type: (Any) -> PWArgs
    return _pw_createString(string)  # type: ignore

_pw_createInt = _lib.pw_createInt
_pw_createInt.restype = PWArgs
_pw_createInt.argtypes = [c_int64]
def pw_createInt(value):
    # type: (Any) -> PWArgs
    return _pw_createInt(value)  # type: ignore

_pw_createUint = _lib.pw_createUint
_pw_createUint.restype = PWArgs
_pw_createUint.argtypes = [c_uint64]
def pw_createUint(value):
    # type: (Any) -> PWArgs
    return _pw_createUint(value)  # type: ignore

_pw_createArray = _lib.pw_createArray
_pw_createArray.restype = PWArgs
_pw_createArray.argtypes = []
def pw_createArray():
    # type: () -> PWArgs
    return _pw_createArray()  # type: ignore

_pw_createMap = _lib.pw_createMap
_pw_createMap.restype = PWArgs
_pw_createMap.argtypes = []
def pw_createMap():
    # type: () -> PWArgs
    return _pw_createMap()  # type: ignore

_pw_addArray = _lib.pw_addArray
_pw_addArray.restype = c_bool
_pw_addArray.argtypes = [POINTER(PWArgs), PWArgs]
def pw_addArray(array, entry):
    # type: (Any, Any) -> c_bool
    return _pw_addArray(array, entry)  # type: ignore

_pw_addMap = _lib.pw_addMap
_pw_addMap.restype = c_bool
_pw_addMap.argtypes = [POINTER(PWArgs), c_char_p, c_uint64, PWArgs]
def pw_addMap(map, entryName, entryNameLength, entry):
    # type: (Any, Any, Any, Any) -> c_bool
    return _pw_addMap(map, entryName, entryNameLength, entry)  # type: ignore

_pw_freeArg = _lib.pw_freeArg
_pw_freeArg.restype = None
_pw_freeArg.argtypes = [POINTER(PWArgs)]
def pw_freeArg(input):
    # type: (Any) -> None
    return _pw_freeArg(input)  # type: ignore

_pw_memAlloc = _lib.pw_memAlloc
_pw_memAlloc.restype = c_void_p
_pw_memAlloc.argtypes = [c_uint64]
def pw_memAlloc(size):
    # type: (Any) -> pointer
    return _pw_memAlloc(size)  # type: ignore

_pw_memRealloc = _lib.pw_memRealloc
_pw_memRealloc.restype = c_void_p
_pw_memRealloc.argtypes = [c_void_p, c_uint64]
def pw_memRealloc(ptr, size):
    # type: (Any, Any) -> pointer
    return _pw_memRealloc(ptr, size)  # type: ignore

_pw_memFree = _lib.pw_memFree
_pw_memFree.restype = None
_pw_memFree.argtypes = [c_void_p]
def pw_memFree(ptr):
    # type: (Any) -> None
    return _pw_memFree(ptr)  # type: ignore

_pw_initString = _lib.pw_initString
_pw_initString.restype = PWArgs
_pw_initString.argtypes = [c_char_p, c_uint64]
def pw_initString(string, length):
    # type: (Any, Any) -> PWArgs
    return _pw_initString(string, length)  # type: ignore

_pw_addMapNoCopy = _lib.pw_addMapNoCopy
_pw_addMapNoCopy.restype = c_bool
_pw_addMapNoCopy.argtypes = [POINTER(PWArgs), c_char_p, c_uint64, PWArgs]
def pw_addMapNoCopy(map, entryName, entryNameLength, entry):
    # type: (Any, Any, Any, Any) -> c_bool
    return _pw_addMapNoCopy(map, entryName, entryNameLength, entry)  # type: ignore
