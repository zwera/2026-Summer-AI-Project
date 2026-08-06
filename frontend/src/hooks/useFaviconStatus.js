import { useEffect } from 'react'
import { checkHealth } from '../api/client.js'

// 백엔드 헬스체크 주기 (ms). 너무 잦으면 불필요한 요청이 쌓이므로 30초로 둔다.
const HEALTH_CHECK_INTERVAL = 30_000
const FAVICON_PATH = '/icons/main_icon.jpg'

let grayscaleDataUrlPromise = null

/**
 * 원본 파비콘 이미지를 캔버스에 그려 회색조(grayscale)로 변환한 data URL을
 * 생성한다. <link rel="icon">에는 CSS filter를 적용할 수 없으므로, 실제
 * 픽셀을 변환한 이미지를 만들어 href를 교체하는 방식을 쓴다. 최초 1회만
 * 변환하고 이후에는 캐시된 Promise를 재사용한다.
 */
function getGrayscaleFaviconDataUrl() {
  if (grayscaleDataUrlPromise) return grayscaleDataUrlPromise

  grayscaleDataUrlPromise = new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0)

      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
      const data = imageData.data
      for (let i = 0; i < data.length; i += 4) {
        // 표준 luminance 가중치로 회색조 변환
        const gray = data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114
        data[i] = gray
        data[i + 1] = gray
        data[i + 2] = gray
      }
      ctx.putImageData(imageData, 0, 0)
      resolve(canvas.toDataURL('image/png'))
    }
    img.onerror = reject
    img.src = FAVICON_PATH
  })

  return grayscaleDataUrlPromise
}

function getFaviconLink() {
  let link = document.querySelector("link[rel='icon']")
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  return link
}

/**
 * 백엔드 서버 상태를 주기적으로 확인해 탭 파비콘을 갈아끼우는 훅.
 * 서버가 정상이면 원본 main_icon, 응답이 없으면 회색조로 변환한 아이콘을
 * 보여준다. 화면에 별도 UI를 그리지 않는 순수 side-effect 훅이다.
 */
export function useFaviconStatus() {
  useEffect(() => {
    let cancelled = false
    const link = getFaviconLink()
    link.type = 'image/jpeg'
    link.href = FAVICON_PATH

    async function updateFavicon() {
      const online = await checkHealth()
      if (cancelled) return

      if (online) {
        link.type = 'image/jpeg'
        link.href = FAVICON_PATH
      } else {
        try {
          const grayUrl = await getGrayscaleFaviconDataUrl()
          if (!cancelled) {
            link.type = 'image/png'
            link.href = grayUrl
          }
        } catch {
          // 회색조 변환에 실패해도(예: 캔버스 미지원) 원본 아이콘을 유지한다.
        }
      }
    }

    updateFavicon()
    const id = setInterval(updateFavicon, HEALTH_CHECK_INTERVAL)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])
}
