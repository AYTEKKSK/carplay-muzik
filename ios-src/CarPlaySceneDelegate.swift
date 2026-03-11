import CarPlay
import AVFoundation
import MediaPlayer
import UIKit

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - CarPlay Delegate
// ─────────────────────────────────────────────────────────────────────────────

class CarPlaySceneDelegate: UIResponder, CPTemplateApplicationSceneDelegate {

    var interfaceController: CPInterfaceController?

    // Shared player manager
    let player = MusicPlayerManager.shared

    // ── Bağlantı kuruldu ──────────────────────────────────────────────────────
    func templateApplicationScene(
        _ templateApplicationScene: CPTemplateApplicationScene,
        didConnect interfaceController: CPInterfaceController
    ) {
        self.interfaceController = interfaceController

        // Ses oturumunu aktifleştir
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)

        // Kök şablon: Tab bar (Listeler + Çalıyor)
        let tabBar = buildTabBarTemplate()
        interfaceController.setRootTemplate(tabBar, animated: false, completion: nil)

        // Global playlist'i yükle
        loadGlobalPlaylist()
    }

    func templateApplicationScene(
        _ templateApplicationScene: CPTemplateApplicationScene,
        didDisconnect interfaceController: CPInterfaceController
    ) {
        self.interfaceController = nil
    }

    // ── Tab Bar ───────────────────────────────────────────────────────────────
    private var playlistListTemplate: CPListTemplate!
    private var nowPlayingTemplate: CPNowPlayingTemplate!
    private var tabBarTemplate: CPTabBarTemplate!

    func buildTabBarTemplate() -> CPTabBarTemplate {
        // Playlist listesi sekmesi
        let loadingItem = CPListItem(text: "Yükleniyor…", detailText: "Lütfen bekleyin")
        playlistListTemplate = CPListTemplate(
            title: "🎵 Müzik",
            sections: [CPListSection(items: [loadingItem])]
        )
        playlistListTemplate.tabImage = UIImage(systemName: "music.note.list")

        // Şu an çalıyor sekmesi
        nowPlayingTemplate = CPNowPlayingTemplate.shared
        nowPlayingTemplate.isUpNextButtonEnabled = true
        nowPlayingTemplate.tabImage = UIImage(systemName: "play.circle.fill")

        tabBarTemplate = CPTabBarTemplate(templates: [
            playlistListTemplate,
            nowPlayingTemplate
        ])
        tabBarTemplate.delegate = self
        return tabBarTemplate
    }

    // ── API: Global Playlist yükle ────────────────────────────────────────────
    func loadGlobalPlaylist() {
        MusicAPI.fetchGlobalPlaylist { [weak self] songs in
            guard let self else { return }
            self.player.queue = songs

            let items: [CPListItem] = songs.enumerated().map { (index, song) in
                let title  = song["title"]   as? String ?? "Bilinmeyen"
                let artist = song["channel"] as? String ?? "YouTube"
                let item = CPListItem(text: title, detailText: artist)
                item.handler = { [weak self] _, completion in
                    self?.player.playAtIndex(index)
                    // Now Playing tabına geç
                    DispatchQueue.main.async {
                        self?.tabBarTemplate.selectTemplate(self!.nowPlayingTemplate, animated: true)
                    }
                    completion()
                }
                return item
            }

            DispatchQueue.main.async {
                self.playlistListTemplate.updateSections([
                    CPListSection(items: items, header: "Herkez'in Şarkıları", sectionIndexTitle: nil)
                ])
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - CPTabBarTemplateDelegate
// ─────────────────────────────────────────────────────────────────────────────

extension CarPlaySceneDelegate: CPTabBarTemplateDelegate {
    func tabBarTemplate(_ tabBarTemplate: CPTabBarTemplate,
                        didSelect selectedTemplate: CPTemplate) {
        // Şu an çalıyor sekmesine geçildiğinde Now Playing şablonunu göster
        if selectedTemplate === nowPlayingTemplate {
            // CPNowPlayingTemplate zaten otomatik güncellenir
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - Music Player Manager (Singleton)
// ─────────────────────────────────────────────────────────────────────────────

class MusicPlayerManager: NSObject {

    static let shared = MusicPlayerManager()

    var avPlayer: AVPlayer?
    var queue: [[String: Any]] = []
    var currentIndex: Int = 0

    private override init() {
        super.init()
        setupRemoteCommands()
    }

    // ── Dizinde şarkı çal ─────────────────────────────────────────────────────
    func playAtIndex(_ index: Int) {
        guard index >= 0 && index < queue.count else { return }
        currentIndex = index
        let song = queue[index]

        let videoId = song["video_id"] as? String ?? ""
        let title   = song["title"]    as? String ?? ""
        let artist  = song["channel"]  as? String ?? ""

        MusicAPI.fetchAudioStreamURL(videoId: videoId) { [weak self] audioURL in
            guard let self, let audioURL else { return }

            DispatchQueue.main.async {
                self.avPlayer?.pause()
                let item = AVPlayerItem(url: audioURL)
                self.avPlayer = AVPlayer(playerItem: item)
                self.avPlayer?.play()

                // Bitince sonraki şarkıya geç
                NotificationCenter.default.addObserver(
                    self,
                    selector: #selector(self.songDidEnd),
                    name: .AVPlayerItemDidPlayToEndTime,
                    object: item
                )

                self.updateNowPlaying(title: title, artist: artist, videoId: videoId)
            }
        }
    }

    @objc private func songDidEnd() {
        playNext()
    }

    func playNext() {
        if currentIndex + 1 < queue.count {
            playAtIndex(currentIndex + 1)
        }
    }

    func playPrevious() {
        if currentIndex > 0 {
            playAtIndex(currentIndex - 1)
        }
    }

    // ── Now Playing Bilgisi Güncelle ──────────────────────────────────────────
    func updateNowPlaying(title: String, artist: String, videoId: String) {
        var info: [String: Any] = [
            MPMediaItemPropertyTitle:          title,
            MPMediaItemPropertyArtist:         artist,
            MPNowPlayingInfoPropertyPlaybackRate: 1.0,
            MPNowPlayingInfoPropertyMediaType: MPNowPlayingInfoMediaType.audio.rawValue
        ]
        MPNowPlayingInfoCenter.default().nowPlayingInfo = info

        // Kapak resmini arka planda yükle
        let thumbURLStr = "https://img.youtube.com/vi/\(videoId)/mqdefault.jpg"
        guard let thumbURL = URL(string: thumbURLStr) else { return }

        URLSession.shared.dataTask(with: thumbURL) { data, _, _ in
            guard let data, let image = UIImage(data: data) else { return }
            let artwork = MPMediaItemArtwork(boundsSize: image.size) { _ in image }
            info[MPMediaItemPropertyArtwork] = artwork
            DispatchQueue.main.async {
                MPNowPlayingInfoCenter.default().nowPlayingInfo = info
            }
        }.resume()
    }

    // ── Uzaktan Kontrol Komutları (CarPlay direksiyonu vs.) ───────────────────
    func setupRemoteCommands() {
        let center = MPRemoteCommandCenter.shared()

        center.playCommand.addTarget { [weak self] _ in
            self?.avPlayer?.play()
            return .success
        }
        center.pauseCommand.addTarget { [weak self] _ in
            self?.avPlayer?.pause()
            return .success
        }
        center.togglePlayPauseCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            if self.avPlayer?.rate == 0 { self.avPlayer?.play() }
            else { self.avPlayer?.pause() }
            return .success
        }
        center.nextTrackCommand.addTarget { [weak self] _ in
            self?.playNext()
            return .success
        }
        center.previousTrackCommand.addTarget { [weak self] _ in
            self?.playPrevious()
            return .success
        }
        center.changePlaybackPositionCommand.addTarget { [weak self] event in
            guard let e = event as? MPChangePlaybackPositionCommandEvent else { return .commandFailed }
            self?.avPlayer?.seek(to: CMTime(seconds: e.positionTime, preferredTimescale: 600))
            return .success
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - Music API Helper
// ─────────────────────────────────────────────────────────────────────────────

struct MusicAPI {

    static let baseURL = "https://app.articnc.online/muzik"

    // Global playlist (şarkılarla)
    static func fetchGlobalPlaylist(completion: @escaping ([[String: Any]]) -> Void) {
        guard let url = URL(string: "\(baseURL)/api/music/playlists/global") else {
            completion([]); return
        }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            guard
                let data,
                let json       = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                let playlist   = json["playlist"]  as? [String: Any],
                let songs      = playlist["songs"] as? [[String: Any]]
            else { completion([]); return }
            completion(songs)
        }.resume()
    }

    // Şarkı için audio stream URL
    static func fetchAudioStreamURL(videoId: String, completion: @escaping (URL?) -> Void) {
        guard let url = URL(string: "\(baseURL)/api/get-audio-stream") else {
            completion(nil); return
        }
        var request = URLRequest(url: url)
        request.httpMethod  = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody    = try? JSONSerialization.data(withJSONObject: ["video_id": videoId])
        request.timeoutInterval = 30

        URLSession.shared.dataTask(with: request) { data, _, _ in
            guard
                let data,
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                let urlStr = json["audio_url"] as? String,
                let audioURL = URL(string: urlStr)
            else { completion(nil); return }
            completion(audioURL)
        }.resume()
    }
}
