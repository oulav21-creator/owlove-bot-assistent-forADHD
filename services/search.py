"""
Сервис для поиска информации (YouTube, Habr).
"""

import os
import requests
import re
from typing import List, Dict
from googleapiclient.discovery import build


def search_youtube(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Поиск видео на YouTube.
    
    Args:
        query: Поисковый запрос
        max_results: Максимальное количество результатов (по умолчанию 5)
    
    Returns:
        Список словарей с title и link
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    
    if not api_key:
        return []
    
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        request = youtube.search().list(
            part='snippet',
            q=query,
            type='video',
            maxResults=max_results,
            videoDuration='long',  # Только длинные видео
            relevanceLanguage='ru',  # Русский язык
            regionCode='RU',  # Регион Россия
            order='viewCount'  # Популярные видео
        )
        
        response = request.execute()
        
        results = []
        for item in response.get('items', []):
            video_id = item['id']['videoId']
            results.append({
                'title': item['snippet']['title'],
                'link': f"https://www.youtube.com/watch?v={video_id}"
            })
        
        return results
    except Exception as e:
        print(f"Ошибка поиска YouTube: {e}")
        return []


def search_web(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """
    Поиск статей на Habr.com через RSS.
    
    Args:
        query: Поисковый запрос
        max_results: Максимальное количество результатов (ограничено до 3)
    
    Returns:
        Список словарей с title и link
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # Используем RSS feed поиска Habr (более надежный способ)
        rss_url = f"https://habr.com/ru/rss/search/?q={requests.utils.quote(query)}&target_type=posts&order=relevance"
        
        try:
            rss_response = requests.get(rss_url, headers=headers, timeout=10)
            rss_response.raise_for_status()
            
            rss_text = rss_response.text
            
            # Парсим RSS - ищем заголовки и ссылки
            # Формат RSS: <title><![CDATA[Заголовок]]></title> и <link>https://habr.com/ru/post/...</link>
            results = []
            
            # Ищем все item блоки
            items = re.findall(r'<item>(.*?)</item>', rss_text, re.DOTALL)
            
            for item in items[:max_results]:
                # Извлекаем заголовок
                title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item)
                # Или альтернативный формат без CDATA
                if not title_match:
                    title_match = re.search(r'<title>(.*?)</title>', item)
                
                # Извлекаем ссылку
                link_match = re.search(r'<link>(https://habr\.com/ru/(?:post|news)/\d+/[^<]*)</link>', item)
                # Или альтернативный формат
                if not link_match:
                    link_match = re.search(r'<link>([^<]+)</link>', item)
                
                if title_match and link_match:
                    title = title_match.group(1).strip()
                    link = link_match.group(1).strip()
                    
                    # Очищаем заголовок от HTML-сущностей
                    title = re.sub(r'&[a-z]+;', '', title)
                    title = title.replace('&nbsp;', ' ').replace('&amp;', '&').strip()
                    
                    if title and link and 'habr.com' in link:
                        results.append({
                            "title": title[:200],
                            "link": link
                        })
            
            if results:
                return results[:max_results]
            
        except Exception as e:
            print(f"Ошибка при парсинге RSS Habr: {e}")
        
        # Если RSS не сработал, пробуем парсить HTML страницы поиска
        try:
            search_url = "https://habr.com/ru/search/"
            params = {
                "q": query,
                "target_type": "posts",
                "order": "relevance"
            }
            
            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            html = response.text
            
            # Ищем ссылки на статьи (формат: /ru/post/123456/ или /ru/news/123456/)
            # И заголовки в тегах <h2> или <a> с классом
            results = []
            seen_links = set()
            
            # Паттерн для поиска ссылок на статьи
            link_pattern = r'href="(https://habr\.com/ru/(?:post|news)/\d+/[^"]*)"'
            links = re.findall(link_pattern, html)
            
            # Для каждой ссылки пытаемся найти заголовок рядом
            for link in links[:max_results * 3]:
                if link in seen_links:
                    continue
                seen_links.add(link)
                
                # Ищем заголовок рядом со ссылкой (в пределах 500 символов)
                link_pos = html.find(link)
                if link_pos != -1:
                    # Ищем заголовок перед ссылкой
                    context = html[max(0, link_pos - 500):link_pos + 200]
                    
                    # Пробуем найти заголовок в разных форматах
                    title_match = re.search(r'<h2[^>]*>([^<]+)</h2>', context)
                    if not title_match:
                        title_match = re.search(r'<a[^>]*href="[^"]*' + re.escape(link.split('/')[-2]) + r'[^"]*"[^>]*>([^<]+)</a>', context)
                    if not title_match:
                        title_match = re.search(r'title="([^"]+)"', context)
                    
                    title = title_match.group(1).strip() if title_match else query
                    
                    # Очищаем заголовок
                    title = re.sub(r'<[^>]+>', '', title)  # Убираем HTML теги
                    title = re.sub(r'&[a-z]+;', '', title)
                    title = title.replace('&nbsp;', ' ').replace('&amp;', '&').strip()
                    
                    if title and len(title) > 5:  # Минимальная длина заголовка
                        results.append({
                            "title": title[:200],
                            "link": link
                        })
                    
                    if len(results) >= max_results:
                        break
            
            return results[:max_results]
            
        except Exception as e:
            print(f"Ошибка при парсинге HTML Habr: {e}")
        
        return []
        
    except Exception as e:
        print(f"Ошибка поиска на Habr: {e}")
        return []


def search_info(query: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Комплексный поиск информации.
    
    Args:
        query: Поисковый запрос
    
    Returns:
        Словарь с ключами 'youtube' и 'web' (статьи с Habr)
    """
    return {
        'youtube': search_youtube(query),
        'web': search_web(query)  # Статьи с Habr.com
    }
