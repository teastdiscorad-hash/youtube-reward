document.addEventListener('DOMContentLoaded', () => {
    // Elements - Primary Video
    const primaryUrlInput = document.getElementById('primaryUrl');
    const btnFetchInfo = document.getElementById('btnFetchInfo');
    const videoInfoBox = document.getElementById('videoInfoBox');
    const videoThumb = document.getElementById('videoThumb');
    const videoTitle = document.getElementById('videoTitle');
    const videoDuration = document.getElementById('videoDuration');

    // Elements - Background Video
    const bgUrlInput = document.getElementById('bgUrl');
    const btnFetchBgInfo = document.getElementById('btnFetchBgInfo');
    const bgVideoInfoBox = document.getElementById('bgVideoInfoBox');
    const bgVideoThumb = document.getElementById('bgVideoThumb');
    const bgVideoTitle = document.getElementById('bgVideoTitle');
    const bgVideoDuration = document.getElementById('bgVideoDuration');

    const layoutCards = document.querySelectorAll('.layout-card');
    const keyTolerance = document.getElementById('keyTolerance');
    const toleranceVal = document.getElementById('toleranceVal');
    
    // Accordion Toggle
    const toggleSettings = document.getElementById('toggleSettings');
    const settingsContent = document.getElementById('settingsContent');
    if (toggleSettings && settingsContent) {
        toggleSettings.addEventListener('click', () => {
            settingsContent.classList.toggle('hidden');
            const icon = toggleSettings.querySelector('.arrow-icon');
            if (icon) {
                icon.classList.toggle('fa-chevron-down');
                icon.classList.toggle('fa-chevron-up');
            }
        });
    }

    const startTime = document.getElementById('startTime');
    const endTime = document.getElementById('endTime');
    
    const btnSubmit = document.getElementById('btnSubmit');

    const statusBox = document.getElementById('statusBox');
    const statusMessage = document.getElementById('statusMessage');
    const progressBar = document.getElementById('progressBar');
    
    const steps = [
        document.querySelector('.step-1'),
        document.querySelector('.step-2'),
        document.querySelector('.step-3')
    ];

    const resultBox = document.getElementById('resultBox');
    const outputVideoPlayer = document.getElementById('outputVideoPlayer');
    const downloadBtn = document.getElementById('downloadBtn');
    const errorBox = document.getElementById('errorBox');
    const errorMessage = document.getElementById('errorMessage');

    // Update tolerance display
    if (keyTolerance && toleranceVal) {
        keyTolerance.addEventListener('input', (e) => {
            toleranceVal.textContent = e.target.value;
        });
    }

    // Layout Selector Cards
    if (layoutCards && layoutCards.length > 0) {
        layoutCards.forEach(card => {
            card.addEventListener('click', () => {
                layoutCards.forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                const radio = card.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;
            });
        });
    }

    // Position Options
    const posOptions = document.querySelectorAll('.pos-option');
    posOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            posOptions.forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
            const radio = opt.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    // 1. Fetch Info - Primary Video
    if (btnFetchInfo && primaryUrlInput) {
        btnFetchInfo.addEventListener('click', async () => {
            const url = primaryUrlInput.value.trim();
            if (!url) {
                alert('يرجى إدخال رابط المقطع الأساسي أولاً');
                primaryUrlInput.focus();
                return;
            }

            btnFetchInfo.disabled = true;
            btnFetchInfo.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري التحقق...';

            try {
                const response = await fetch(`/api/info?url=${encodeURIComponent(url)}`);
                const data = await response.json();

                if (data.success && data.info) {
                    if (videoThumb) videoThumb.src = data.info.thumbnail || '';
                    if (videoTitle) videoTitle.textContent = data.info.title || 'مقطع الأساس';
                    if (videoDuration) videoDuration.textContent = data.info.duration_string || 'غير محدد';
                    if (videoInfoBox) videoInfoBox.classList.remove('hidden');
                } else {
                    alert('تعذر جلب معلومات المقطع: ' + (data.detail || 'تأكد من صحة الرابط.'));
                }
            } catch (err) {
                alert('حدث خطأ أثناء فحص الرابط.');
            } finally {
                btnFetchInfo.disabled = false;
                btnFetchInfo.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> فحص الرابط';
            }
        });
    }

    // 2. Fetch Info - Background Video
    if (btnFetchBgInfo && bgUrlInput) {
        btnFetchBgInfo.addEventListener('click', async () => {
            const url = bgUrlInput.value.trim();
            if (!url) {
                alert('يرجى إدخال رابط مقطع الخلفية أولاً');
                bgUrlInput.focus();
                return;
            }

            btnFetchBgInfo.disabled = true;
            btnFetchBgInfo.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري التحقق...';

            try {
                const response = await fetch(`/api/info?url=${encodeURIComponent(url)}`);
                const data = await response.json();

                if (data.success && data.info) {
                    if (bgVideoThumb) bgVideoThumb.src = data.info.thumbnail || '';
                    if (bgVideoTitle) bgVideoTitle.textContent = data.info.title || 'مقطع الخلفية';
                    if (bgVideoDuration) bgVideoDuration.textContent = data.info.duration_string || 'غير محدد';
                    if (bgVideoInfoBox) bgVideoInfoBox.classList.remove('hidden');
                } else {
                    alert('تعذر جلب معلومات مقطع الخلفية: ' + (data.detail || 'تأكد من صحة الرابط.'));
                }
            } catch (err) {
                alert('حدث خطأ أثناء فحص الرابط.');
            } finally {
                btnFetchBgInfo.disabled = false;
                btnFetchBgInfo.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> فحص الرابط';
            }
        });
    }

    // 3. Submit Form
    if (btnSubmit) {
        btnSubmit.addEventListener('click', async () => {
            const primaryUrl = primaryUrlInput ? primaryUrlInput.value.trim() : '';
            const bgUrl = bgUrlInput ? bgUrlInput.value.trim() : '';
            
            if (!primaryUrl) {
                alert('يرجى إدخال رابط المقطع الأساسي.');
                if (primaryUrlInput) primaryUrlInput.focus();
                return;
            }
            if (!bgUrl) {
                alert('يرجى إدخال رابط مقطع الخلفية.');
                if (bgUrlInput) bgUrlInput.focus();
                return;
            }

            const selectedLayoutRadio = document.querySelector('input[name="layout"]:checked');
            const layout = selectedLayoutRadio ? selectedLayoutRadio.value : 'black_screen_transparent';
            const tol = keyTolerance ? keyTolerance.value : 0.25;
            const posInput = document.querySelector('input[name="video_position"]:checked');
            const pos = posInput ? posInput.value : 'center';
            
            const sTime = startTime ? (startTime.value || 0) : 0;
            const eTime = endTime ? (endTime.value || '') : '';

            // Reset UI
            btnSubmit.disabled = true;
            if (statusBox) statusBox.classList.remove('hidden');
            if (resultBox) resultBox.classList.add('hidden');
            if (errorBox) errorBox.classList.add('hidden');
            
            if (steps) {
                steps.forEach(s => s && s.classList.remove('active', 'completed'));
                if (steps[0]) steps[0].classList.add('active');
            }
            if (progressBar) progressBar.style.width = '10%';
            if (statusMessage) statusMessage.textContent = 'جاري وضع الطلب في قائمة الانتظار...';
            
            if (statusBox) statusBox.scrollIntoView({ behavior: 'smooth' });

            const formData = new FormData();
            formData.append('primary_url', primaryUrl);
            formData.append('bg_url', bgUrl);
            formData.append('layout', layout);
            formData.append('key_tolerance', tol);
            formData.append('video_position', pos);
            formData.append('start_time', sTime);
            if (eTime) formData.append('end_time', eTime);

            try {
                const response = await fetch('/api/generate-video', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.success && data.task_id) {
                    pollTaskStatus(data.task_id);
                } else {
                    showError(data.detail || 'فشل بدء الطلب. يرجى المحاولة مرة أخرى.');
                }
            } catch (err) {
                showError('تعذر الاتصال بالخادم.');
            }
        });
    }

    function pollTaskStatus(taskId) {
        const MAX_POLLING_ATTEMPTS = 300; // 10 minutes at 2s interval
        const MAX_CONSECUTIVE_ERRORS = 5;
        let pollCount = 0;
        let errorCount = 0;

        const interval = setInterval(async () => {
            pollCount++;

            if (pollCount >= MAX_POLLING_ATTEMPTS) {
                clearInterval(interval);
                showError('انتهى وقت الانتظار. استغرقت العملية وقتاً أطول من المعتاد.');
                return;
            }

            try {
                const res = await fetch(`/api/status/${taskId}`);
                if (!res.ok) throw new Error('Network response was not ok');
                const data = await res.json();
                
                // Reset error count on successful request
                errorCount = 0; 

                if (data.status === 'downloading') {
                    if (statusMessage) statusMessage.textContent = data.message;
                    if (progressBar) progressBar.style.width = '30%';
                    if (steps[0]) steps[0].classList.add('active');
                } else if (data.status === 'processing') {
                    if (statusMessage) statusMessage.textContent = data.message;
                    if (progressBar) progressBar.style.width = '70%';
                    if (steps[0]) steps[0].classList.replace('active', 'completed');
                    if (steps[1]) steps[1].classList.add('active');
                } else if (data.status === 'completed') {
                    clearInterval(interval);
                    if (progressBar) progressBar.style.width = '100%';
                    if (steps[1]) steps[1].classList.replace('active', 'completed');
                    if (steps[2]) steps[2].classList.add('completed');
                    
                    setTimeout(() => {
                        if (statusBox) statusBox.classList.add('hidden');
                        if (resultBox) resultBox.classList.remove('hidden');
                        if (outputVideoPlayer) outputVideoPlayer.src = data.download_url;
                        if (downloadBtn) downloadBtn.href = data.download_url;
                        if (btnSubmit) btnSubmit.disabled = false;
                        if (resultBox) resultBox.scrollIntoView({ behavior: 'smooth' });
                    }, 1000);
                    
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    showError(data.message || 'حدث خطأ أثناء المعالجة.');
                }
            } catch (e) {
                console.error('Polling error:', e);
                errorCount++;
                if (errorCount >= MAX_CONSECUTIVE_ERRORS) {
                    clearInterval(interval);
                    showError('فقد الاتصال بالخادم. يرجى المحاولة مرة أخرى.');
                }
            }
        }, 2000);
    }

    function showError(msg) {
        if (statusBox) statusBox.classList.add('hidden');
        if (errorBox && errorMessage) {
            errorBox.classList.remove('hidden');
            errorMessage.textContent = msg;
            errorBox.scrollIntoView({ behavior: 'smooth' });
        } else {
            alert(msg);
        }
        if (btnSubmit) btnSubmit.disabled = false;
    }
});
