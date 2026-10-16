package org.opensource.lifealgo

import android.app.Application
import androidx.room.Room
import org.opensource.lifealgo.data.ContentRepository
import org.opensource.lifealgo.data.LifeAlgoDatabase
import org.opensource.lifealgo.data.SettingsRepository
import org.opensource.lifealgo.data.UserStateRepository
import org.opensource.lifealgo.reminder.Notifications

class LifeAlgoApp : Application() {

    lateinit var content: ContentRepository
        private set

    lateinit var userState: UserStateRepository
        private set

    lateinit var settings: SettingsRepository
        private set

    lateinit var database: LifeAlgoDatabase
        private set

    override fun onCreate() {
        super.onCreate()
        content = ContentRepository(this)
        settings = SettingsRepository(this)
        database = Room.databaseBuilder(this, LifeAlgoDatabase::class.java, "lifealgo.db")
            .fallbackToDestructiveMigration()
            .build()
        userState = UserStateRepository(database)
        Notifications.ensureChannel(this)
    }

    companion object {
        fun from(context: android.content.Context): LifeAlgoApp =
            context.applicationContext as LifeAlgoApp
    }
}
