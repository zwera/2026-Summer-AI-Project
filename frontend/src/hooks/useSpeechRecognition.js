import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * 브라우저 내장 Web Speech API(SpeechRecognition)를 감싼 훅.
 * 별도 서버/API 키 없이 동작하며, Chrome/Edge 등 Chromium 계열에서 지원한다
 * (Firefox는 미지원). 지원하지 않는 브라우저에서는 isSupported=false를 반환해
 * 호출부가 UI를 비활성화할 수 있게 한다.
 *
 * @param {object} options
 * @param {(text: string) => void} options.onResult 최종 인식 결과가 나올 때 호출
 * @param {string} [options.lang] 인식 언어 (기본값 'ko-KR')
 */
export function useSpeechRecognition({ onResult, lang = 'ko-KR' } = {}) {
  const SpeechRecognitionClass =
    typeof window !== 'undefined'
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null
  const isSupported = Boolean(SpeechRecognitionClass)

  const [isListening, setIsListening] = useState(false)
  const [interimText, setInterimText] = useState('')
  const [error, setError] = useState(null)
  const recognitionRef = useRef(null)
  const onResultRef = useRef(onResult)

  useEffect(() => {
    onResultRef.current = onResult
  }, [onResult])

  useEffect(() => {
    if (!isSupported) return

    const recognition = new SpeechRecognitionClass()
    recognition.lang = lang
    recognition.continuous = false
    recognition.interimResults = true

    recognition.onresult = (event) => {
      let finalText = ''
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          finalText += transcript
        } else {
          interim += transcript
        }
      }
      if (finalText) {
        onResultRef.current?.(finalText.trim())
        setInterimText('')
      } else {
        setInterimText(interim)
      }
    }

    recognition.onerror = (event) => {
      const messages = {
        'not-allowed': '마이크 권한이 거부되었습니다. 브라우저 설정에서 허용해주세요.',
        'no-speech': '음성이 감지되지 않았습니다. 다시 시도해주세요.',
        network: '네트워크 오류로 음성 인식에 실패했습니다.',
      }
      setError(messages[event.error] || `음성 인식 오류: ${event.error}`)
      setIsListening(false)
    }

    recognition.onend = () => {
      setIsListening(false)
      setInterimText('')
    }

    recognitionRef.current = recognition

    return () => {
      recognition.onresult = null
      recognition.onerror = null
      recognition.onend = null
      recognition.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSupported, lang])

  const start = useCallback(() => {
    if (!recognitionRef.current || isListening) return
    setError(null)
    try {
      recognitionRef.current.start()
      setIsListening(true)
    } catch {
      // 이미 시작된 상태에서 start()를 다시 호출하면 예외가 나는데,
      // 사용자 입장에서는 무시해도 안전한 상황이다.
    }
  }, [isListening])

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
  }, [])

  const toggle = useCallback(() => {
    if (isListening) stop()
    else start()
  }, [isListening, start, stop])

  return { isSupported, isListening, interimText, error, start, stop, toggle }
}
